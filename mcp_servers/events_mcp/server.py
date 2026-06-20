"""Events-MCP — FastMCP-SSE-Server fuer fachliche Events am Vorgang.

Plan 08. Eigene Domaene, weil Events polymorph an beliebige Entities
haengen (nicht nur Process — Plan 08 Offene Frage 3). Vier Tools:

    event_log     — manueller Eintrag in der Bedeutungs-Timeline
    event_list    — chronologisch gefiltert
    event_get     — Einzel-Lookup
    event_delete  — Soft-Delete (Edit gibt es bewusst nicht; Korrektur =
                    neues Event)

Auto-Erzeugung aus dem Change-Log laeuft NICHT hier, sondern im
``lib.audit_to_event``-Listener — wenn der Server-Prozess die Hooks
installiert, materialisieren auch ueber dieses MCP ausgeloeste
Status-Wechsel automatisch ``status_changed``-Events.
"""
import os
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from lib.audit import install_change_log_hooks
from lib.audit_to_event import install_event_hooks
from lib.business_events import BUSINESS_EVENT_TYPES, log_event
from lib.db import session_for_tenant
from lib.entities.tenant import BusinessEvent
from lib.logging import get_logger
from lib.polymorphic import validate_target
from lib.tenant_context import set_tenant

logger = get_logger(__name__)

mcp = FastMCP("wai-events", host="0.0.0.0", port=8001)

MCP_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Manifest (Plan 05)
# ---------------------------------------------------------------------------


@mcp.tool()
def manifest() -> dict:
    """Self-Description fuer Agent-Discovery (Vision §21)."""
    tool_names = ["event_log", "event_list", "event_get", "event_delete"]
    return {
        "name": "wai-events",
        "version": MCP_VERSION,
        "kind": "tool",
        "description": (
            "Fachliche Events am Vorgang — kuratierte Bedeutungs-Timeline. "
            "Polymorpher Anker an beliebige Entities; Auto-Events aus dem "
            "Change-Log materialisieren parallel (lib/audit_to_event.py)."
        ),
        "entities": ["core.event"],
        "tools": [{"name": n, "kind": "function"} for n in tool_names],
        "event_type_conventions": list(BUSINESS_EVENT_TYPES),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug() -> str:
    return os.environ.get("WAI_TENANT_SLUG_DEFAULT", "demo")


def _to_dict(obj: BusinessEvent) -> dict:
    out: dict = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        out[col.name] = val
    return out


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        logger.warning("ungueltiges datetime-format: %r", raw)
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def event_log(
    target_cls: str,
    target_id: int,
    event_type: str = "manual_entry",
    title: str = "",
    body: str = "",
    happened_at: str = "",
    data: dict = {},
) -> dict:
    """Schreibt ein manuelles BusinessEvent.

    target_cls + target_id sind PFLICHT (Plan 08 Offene Frage 4 —
    Anker-Pflicht, keine globalen Events). actor_type/agent_name/trace_uid
    werden aus dem Tenant-Context gefuellt (siehe lib.business_events).
    """
    slug = _slug()
    set_tenant(slug)

    target_cls = (target_cls or "").strip()
    if not target_cls or int(target_id or 0) <= 0:
        return {"error": "target_cls und target_id (>0) sind pflicht"}
    try:
        validate_target(target_cls, int(target_id))
    except ValueError as exc:
        return {"error": f"Anker ungueltig: {exc}"}

    try:
        new_id = log_event(
            target_cls=target_cls,
            target_id=int(target_id),
            event_type=(event_type or "manual_entry").strip(),
            title=title or "",
            body=body or "",
            happened_at=_parse_dt(happened_at),
            data=data or {},
            source="manual",
            source_ref="",
            tenant_slug=slug,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    with session_for_tenant(slug) as s:
        obj = s.get(BusinessEvent, new_id)
        if obj is None:
            return {"id": new_id}
        return _to_dict(obj)


@mcp.tool()
def event_get(id: int) -> dict:
    """Einzel-Lookup. Liefert auch soft-geloeschte Events (UI kann filtern)."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(BusinessEvent, int(id))
        if obj is None:
            return {"error": f"event id={id} nicht gefunden"}
        return _to_dict(obj)


@mcp.tool()
def event_list(
    target_cls: str = "",
    target_id: int = 0,
    event_type: str = "",
    trace_uid: str = "",
    since: str = "",
    until: str = "",
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list:
    """Chronologisch absteigend nach happened_at, mit Equality-/Range-Filtern."""
    limit = max(1, min(int(limit or 50), 500))
    offset = max(0, int(offset or 0))

    with session_for_tenant(_slug()) as s:
        stmt = select(BusinessEvent)
        if not include_deleted:
            stmt = stmt.where(BusinessEvent.is_deleted.is_(False))
        if target_cls:
            stmt = stmt.where(BusinessEvent.target_cls == target_cls)
        if int(target_id or 0) > 0:
            stmt = stmt.where(BusinessEvent.target_id == int(target_id))
        if event_type:
            stmt = stmt.where(BusinessEvent.event_type == event_type)
        if trace_uid:
            stmt = stmt.where(BusinessEvent.trace_uid == trace_uid)
        dt_since = _parse_dt(since)
        if dt_since is not None:
            stmt = stmt.where(BusinessEvent.happened_at >= dt_since)
        dt_until = _parse_dt(until)
        if dt_until is not None:
            stmt = stmt.where(BusinessEvent.happened_at <= dt_until)
        stmt = (
            stmt.order_by(BusinessEvent.happened_at.desc(), BusinessEvent.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = s.execute(stmt).scalars().all()
        return [_to_dict(r) for r in rows]


@mcp.tool()
def event_delete(id: int) -> dict:
    """Soft-Delete (is_deleted=True). Korrektur passiert konventionell ueber
    soft-delete + neues Event — kein Edit-Tool (Audit-Charakter, Plan 08
    Schnittweise).
    """
    with session_for_tenant(_slug()) as s:
        obj = s.get(BusinessEvent, int(id))
        if obj is None:
            return {"error": f"event id={id} nicht gefunden"}
        obj.is_deleted = True
        s.commit()
        logger.info("event_delete id=%s", obj.id)
        return {"ok": True, "id": int(obj.id)}


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    # Reihenfolge wichtig: Auto-Event-Listener MUSS nach Change-Log-Hook
    # registriert sein (Plan 08 Offene Frage 5).
    install_change_log_hooks()
    install_event_hooks()
    logger.info(
        "Starte wai-events-mcp auf Port %s via SSE (tenant=%s)", port, _slug()
    )
    mcp.run(transport="sse")
