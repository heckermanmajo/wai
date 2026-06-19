"""Debug-MCP — FastMCP-SSE-Server fuer Einblick in das WAI-Datenmodell.

Tools fuer Introspektion ueber alle drei logischen DBs (admin_db,
logging_db, tenant_<slug>): Listen der registrierten Entitaeten, Schema-
Beschreibungen, Row-Counts, Sample-Rows (mit Redaction sensibler Felder),
aktuelle Tenant-Info und juengste Events aus dem logging_db.

Bewusst lesend: keine Mutationen, keine schemaaendernden Operationen.
Antworten sind JSON-serialisierbar — datetimes werden zu ISO-Strings.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError

from lib.base import AdminBase, LoggingBase, TenantBase
from lib.db import (
    session_for_admin,
    session_for_logging,
    session_for_tenant,
    tenant_db_url,
)

# Wichtig: Entities importieren, damit register_entity() ausgefuehrt wird
# und die Tabellen an die jeweiligen MetaData-Objekte gehaengt werden.
import lib.entities.admin  # noqa: F401  (Seiteneffekt: Modelle registrieren)
import lib.entities.tenant  # noqa: F401  (Seiteneffekt: Modelle registrieren)
try:  # logging-Entities sind optional / werden spaeter befuellt
    import lib.entities.logging  # noqa: F401
except Exception:  # pragma: no cover
    pass

from lib.logging import get_logger
from lib.polymorphic import list_entities as _registered_entities
from lib.polymorphic import resolve_target_cls

logger = get_logger(__name__)

mcp = FastMCP("wai-debug", host="0.0.0.0", port=8001)

VERSION = "0.1.0"
REDACT_KEYS = {"api_key", "password", "password_hash", "token", "secret"}
MAX_SAMPLE_LIMIT = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug() -> str:
    return os.environ.get("WAI_TENANT_SLUG_DEFAULT", "demo")


def _db_for_cls(cls: type) -> str:
    """Ordnet eine Modell-Klasse einer der drei DBs zu."""
    md = getattr(getattr(cls, "__table__", None), "metadata", None)
    if md is AdminBase.metadata:
        return "admin"
    if md is LoggingBase.metadata:
        return "logging"
    if md is TenantBase.metadata:
        return "tenant"
    return "unknown"


def _session_for_db(db: str):
    if db == "admin":
        return session_for_admin()
    if db == "logging":
        return session_for_logging()
    if db == "tenant":
        return session_for_tenant(_slug())
    raise ValueError(f"unbekannte DB-Zuordnung: {db!r}")


def _json_value(val: Any) -> Any:
    """datetime -> ISO-String, sonst unveraendert (Hauptsache JSON-tauglich)."""
    if isinstance(val, datetime):
        return val.isoformat()
    return val


def _row_to_dict(obj: Any) -> dict:
    """SQLAlchemy-ORM-Objekt -> plain dict mit Redaction sensibler Felder."""
    out: dict = {}
    for col in obj.__table__.columns:
        name = col.name
        val = getattr(obj, name)
        if name in REDACT_KEYS and val not in (None, ""):
            out[name] = "<redacted>"
        else:
            out[name] = _json_value(val)
    return out


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_entities() -> list:
    """Liste aller via @register_entity registrierten Klassen."""
    result: list[dict] = []
    for alias, cls in _registered_entities().items():
        result.append(
            {
                "alias": alias,
                "table_name": cls.__tablename__,
                "db": _db_for_cls(cls),
            }
        )
    result.sort(key=lambda r: (r["db"], r["alias"]))
    return result


@mcp.tool()
def describe_entity(alias: str) -> dict:
    """Schema einer Entity per Alias — Spalten mit Typ/Nullable/Default."""
    cls = resolve_target_cls(alias)
    if cls is None:
        return {"error": f"alias {alias!r} nicht registriert"}
    cols: list[dict] = []
    for col in cls.__table__.columns:
        default = None
        if col.default is not None:
            default = repr(getattr(col.default, "arg", col.default))
        elif col.server_default is not None:
            default = repr(getattr(col.server_default, "arg", col.server_default))
        cols.append(
            {
                "name": col.name,
                "type": str(col.type),
                "nullable": bool(col.nullable),
                "default": default,
            }
        )
    return {
        "alias": alias,
        "table_name": cls.__tablename__,
        "db": _db_for_cls(cls),
        "columns": cols,
    }


@mcp.tool()
def count_rows(alias: str) -> dict:
    """SELECT count(*) WHERE is_deleted=false fuer die Entity per Alias."""
    cls = resolve_target_cls(alias)
    if cls is None:
        return {"error": f"alias {alias!r} nicht registriert"}
    db = _db_for_cls(cls)
    if db == "unknown":
        return {"error": f"keine DB-Zuordnung fuer {alias!r}"}
    try:
        with _session_for_db(db) as s:
            stmt = select(func.count()).select_from(cls.__table__)
            if "is_deleted" in cls.__table__.columns:
                stmt = stmt.where(cls.__table__.c.is_deleted.is_(False))
            count = s.execute(stmt).scalar_one()
        return {"alias": alias, "db": db, "count": int(count)}
    except ProgrammingError as exc:
        logger.warning("count_rows: tabelle fehlt fuer %s: %s", alias, exc)
        return {"alias": alias, "db": db, "count": 0, "note": "Tabelle existiert nicht"}


@mcp.tool()
def sample_rows(alias: str, limit: int = 5) -> list:
    """Erste n Rows (limit <= 50) — sensible Felder werden redigiert."""
    cls = resolve_target_cls(alias)
    if cls is None:
        return [{"error": f"alias {alias!r} nicht registriert"}]
    db = _db_for_cls(cls)
    if db == "unknown":
        return [{"error": f"keine DB-Zuordnung fuer {alias!r}"}]
    n = max(1, min(int(limit or 5), MAX_SAMPLE_LIMIT))
    try:
        with _session_for_db(db) as s:
            stmt = select(cls)
            if "is_deleted" in cls.__table__.columns:
                stmt = stmt.where(cls.__table__.c.is_deleted.is_(False))
            stmt = stmt.limit(n)
            rows = s.execute(stmt).scalars().all()
        return [_row_to_dict(r) for r in rows]
    except ProgrammingError as exc:
        logger.warning("sample_rows: tabelle fehlt fuer %s: %s", alias, exc)
        return [{"error": "Tabelle existiert nicht", "alias": alias}]


@mcp.tool()
def current_tenant_info() -> dict:
    """Aktiver Tenant-Slug, DB-URL und Row-Counts pro Tenant-Tabelle."""
    slug = _slug()
    try:
        url = tenant_db_url(slug)
    except Exception as exc:  # noqa: BLE001
        return {"slug": slug, "error": f"konnte db-url nicht aufloesen: {exc}"}
    counts: dict[str, Any] = {}
    try:
        with session_for_tenant(slug) as s:
            for table in TenantBase.metadata.tables.values():
                stmt = select(func.count()).select_from(table)
                if "is_deleted" in table.columns:
                    stmt = stmt.where(table.c.is_deleted.is_(False))
                try:
                    counts[table.name] = int(s.execute(stmt).scalar_one())
                except ProgrammingError:
                    s.rollback()
                    counts[table.name] = None  # Tabelle fehlt (noch nicht migriert)
    except Exception as exc:  # noqa: BLE001
        return {"slug": slug, "db_url": url, "error": f"db nicht erreichbar: {exc}"}
    return {"slug": slug, "db_url": url, "counts": counts}


@mcp.tool()
def recent_events(limit: int = 50, since_minutes: int = 60) -> list:
    """Juengste Eintraege aus logging_db.event_log — falls die Tabelle existiert."""
    n = max(1, min(int(limit or 50), 500))
    minutes = max(1, int(since_minutes or 60))
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    try:
        with session_for_logging() as s:
            stmt = text(
                "SELECT * FROM event_log "
                "WHERE created_at >= :cutoff "
                "ORDER BY created_at DESC LIMIT :limit"
            )
            try:
                result = s.execute(stmt, {"cutoff": cutoff, "limit": n})
            except ProgrammingError:
                s.rollback()
                return [{"note": "event_log existiert nicht"}]
            rows = result.mappings().all()
        return [{k: _json_value(v) for k, v in row.items()} for row in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("recent_events fehlgeschlagen: %s", exc)
        return [{"error": str(exc)}]


@mcp.tool()
def ping() -> dict:
    """Health-/Sanity-Check — gibt Zeitstempel und Version zurueck."""
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "service": "wai-debug-mcp",
    }


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    logger.info(
        "Starte wai-debug-mcp auf Port %s via SSE (tenant=%s)", port, _slug()
    )
    mcp.run(transport="sse")
