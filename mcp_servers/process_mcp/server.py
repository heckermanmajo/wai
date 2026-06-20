"""Process-MCP — FastMCP-SSE-Server fuer die Vorgangs-Entitaet.

Plan 07. Eigene Domaene (anlassgetriebene Arbeitseinheit), klar getrennt
von CRM. Hat einen polymorphen Kunden-Anker (customer_cls/customer_id),
typischerweise crm.account, aber offen fuer Contact/Lead.

Jeder Tool-Call laeuft in einer eigenen session_for_tenant(slug)-Session.
Status-Aenderungen validieren gegen settings.resolve("process.status.allowed_values")
und setzen closed_at automatisch, wenn der neue Status zu den
closed_values (Default: abgeschlossen/abgebrochen) zaehlt.

Bewusst keine FK-Checks: project_id / parent_id / assignee_user_id /
owner_user_id sind nackte Integer-Refs (Repo-Konvention).
"""
import os
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from lib.db import session_for_tenant
from lib.entities.tenant import Process
from lib.logging import get_logger
from lib.polymorphic import validate_target
from lib.settings import resolve as settings_resolve
from lib.tenant_context import set_tenant

logger = get_logger(__name__)

mcp = FastMCP("wai-process", host="0.0.0.0", port=8001)

MCP_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Manifest (Plan 05)
# ---------------------------------------------------------------------------


@mcp.tool()
def manifest() -> dict:
    """Self-Description fuer Agent-Discovery (Vision §21)."""
    tool_names = [
        "create_process",
        "get_process",
        "list_processes",
        "update_process",
        "set_status",
        "link_to_project",
        "link_to_customer",
        "archive_process",
        "allowed_status_values",
    ]
    return {
        "name": "wai-process",
        "version": MCP_VERSION,
        "kind": "tool",
        "description": (
            "Verwaltung von Vorgaengen (anlassgetriebene Arbeitseinheiten). "
            "Polymorpher Kunden-Anker; status validiert gegen Settings."
        ),
        "entities": ["core.process"],
        "tools": [{"name": n, "kind": "function"} for n in tool_names],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug() -> str:
    return os.environ.get("WAI_TENANT_SLUG_DEFAULT", "demo")


def _to_dict(obj: Process) -> dict:
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


def _allowed_status(slug: str, process_id: int | None = None) -> list[str]:
    """Loest die erlaubten Status-Werte ueber Settings-Hierarchie auf."""
    set_tenant(slug)
    val = settings_resolve(
        "process.status.allowed_values",
        tenant=slug,
        entity_cls="core.process",
        entity_id=process_id or 0,
    )
    if isinstance(val, list):
        return [str(v) for v in val]
    return []


def _closed_status(slug: str) -> set[str]:
    set_tenant(slug)
    val = settings_resolve(
        "process.status.closed_values",
        tenant=slug,
        entity_cls="core.process",
    )
    if isinstance(val, list):
        return {str(v) for v in val}
    return set()


def _maybe_set_closed_at(process: Process, new_status: str, closed_values: set[str]) -> None:
    """closed_at-Automatik: wird gesetzt beim Wechsel in einen closed-Status,
    geloescht beim Wechsel zurueck in einen offenen.
    """
    if new_status in closed_values and process.closed_at is None:
        process.closed_at = datetime.now(timezone.utc)
    elif new_status not in closed_values and process.closed_at is not None:
        process.closed_at = None


def _validate_customer(cls_alias: str, target_id: int) -> None:
    """Wrap validate_target um konsistente Fehlerklasse."""
    try:
        validate_target(cls_alias or "", int(target_id or 0))
    except ValueError as exc:
        raise ValueError(f"Kunden-Anker ungueltig: {exc}") from exc


# ---------------------------------------------------------------------------
# CRUD-Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def create_process(
    name: str,
    description: str = "",
    kind: str = "",
    priority: str = "normal",
    status: str = "neu",
    project_id: int = 0,
    parent_id: int = 0,
    customer_cls: str = "",
    customer_id: int = 0,
    owner_user_id: int = 0,
    assignee_user_id: int = 0,
    due_at: str = "",
) -> dict:
    """Legt einen neuen Vorgang an. Validiert customer_cls/customer_id
    polymorph und status gegen die erlaubten Werte.
    """
    if not (name or "").strip():
        return {"error": "name ist pflicht"}

    slug = _slug()
    _validate_customer(customer_cls, customer_id)

    allowed = _allowed_status(slug)
    if allowed and status not in allowed:
        return {
            "error": f"status {status!r} nicht erlaubt — erlaubt: {allowed}",
        }

    closed_values = _closed_status(slug)

    with session_for_tenant(slug) as s:
        obj = Process(
            name=name.strip(),
            description=description or "",
            kind=(kind or "").strip(),
            priority=(priority or "normal"),
            status=status,
            project_id=int(project_id or 0),
            parent_id=int(parent_id or 0),
            customer_cls=customer_cls or "",
            customer_id=int(customer_id or 0),
            owner_user_id=int(owner_user_id or 0),
            assignee_user_id=int(assignee_user_id or 0),
            due_at=_parse_dt(due_at),
        )
        _maybe_set_closed_at(obj, status, closed_values)
        s.add(obj)
        s.commit()
        s.refresh(obj)
        logger.info("process_create id=%s name=%s", obj.id, obj.name)
        return _to_dict(obj)


@mcp.tool()
def get_process(id: int) -> dict:
    """Vorgang per id."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(Process, int(id))
        if obj is None or obj.is_deleted:
            return {"error": f"process id={id} nicht gefunden"}
        return _to_dict(obj)


@mcp.tool()
def list_processes(
    status: str = "",
    assignee_user_id: int = 0,
    project_id: int = 0,
    parent_id: int = 0,
    customer_cls: str = "",
    customer_id: int = 0,
    kind: str = "",
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list:
    """Liste mit einfachen Equality-Filtern. Default schliesst soft-deleted aus."""
    limit = max(1, min(int(limit or 50), 500))
    offset = max(0, int(offset or 0))

    with session_for_tenant(_slug()) as s:
        stmt = select(Process)
        if not include_deleted:
            stmt = stmt.where(Process.is_deleted.is_(False))
        if status:
            stmt = stmt.where(Process.status == status)
        if assignee_user_id:
            stmt = stmt.where(Process.assignee_user_id == int(assignee_user_id))
        if project_id:
            stmt = stmt.where(Process.project_id == int(project_id))
        if parent_id:
            stmt = stmt.where(Process.parent_id == int(parent_id))
        if customer_cls:
            stmt = stmt.where(Process.customer_cls == customer_cls)
        if customer_id:
            stmt = stmt.where(Process.customer_id == int(customer_id))
        if kind:
            stmt = stmt.where(Process.kind == kind)
        stmt = stmt.order_by(Process.id.desc()).limit(limit).offset(offset)
        rows = s.execute(stmt).scalars().all()
        return [_to_dict(r) for r in rows]


# Felder, die ueber update_process patchbar sind. Whitelist verhindert,
# dass owner/created_at/is_deleted versehentlich ueber den generischen
# Patch-Weg geaendert werden — dafuer gibt es eigene Tools.
_PATCHABLE_FIELDS: set[str] = {
    "name",
    "description",
    "status",
    "priority",
    "kind",
    "assignee_user_id",
    "project_id",
    "parent_id",
    "due_at",
}


@mcp.tool()
def update_process(id: int, patch: dict = {}) -> dict:
    """Generischer Patch fuer ein Process. Whitelist siehe _PATCHABLE_FIELDS.

    Wenn ``status`` im Patch ist, gilt dieselbe Validierungs- und
    closed_at-Logik wie in ``set_status``.
    """
    patch = patch or {}
    if not isinstance(patch, dict):
        return {"error": "patch muss ein Objekt sein"}

    slug = _slug()
    unknown = [k for k in patch.keys() if k not in _PATCHABLE_FIELDS]
    if unknown:
        return {"error": f"Felder nicht patchbar: {unknown}"}

    with session_for_tenant(slug) as s:
        obj = s.get(Process, int(id))
        if obj is None or obj.is_deleted:
            return {"error": f"process id={id} nicht gefunden"}

        if "status" in patch:
            new_status = str(patch["status"])
            allowed = _allowed_status(slug, obj.id)
            if allowed and new_status not in allowed:
                return {
                    "error": f"status {new_status!r} nicht erlaubt — erlaubt: {allowed}",
                }
            closed_values = _closed_status(slug)
            obj.status = new_status
            _maybe_set_closed_at(obj, new_status, closed_values)

        for field, val in patch.items():
            if field == "status":
                continue
            if field == "due_at":
                obj.due_at = _parse_dt(str(val) if val else "")
                continue
            if field in ("assignee_user_id", "project_id", "parent_id"):
                setattr(obj, field, int(val or 0))
                continue
            setattr(obj, field, val or "")

        s.commit()
        s.refresh(obj)
        logger.info("process_update id=%s patch_keys=%s", obj.id, list(patch.keys()))
        return _to_dict(obj)


@mcp.tool()
def set_status(id: int, status: str) -> dict:
    """Komfort-Setter mit Validierung + closed_at-Automatik."""
    return update_process(int(id), {"status": str(status)})


@mcp.tool()
def link_to_project(process_id: int, project_id: int) -> dict:
    """Setzt process.project_id (0 = aushaengen)."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(Process, int(process_id))
        if obj is None or obj.is_deleted:
            return {"error": f"process id={process_id} nicht gefunden"}
        obj.project_id = int(project_id or 0)
        s.commit()
        s.refresh(obj)
        return _to_dict(obj)


@mcp.tool()
def link_to_customer(process_id: int, customer_cls: str, customer_id: int) -> dict:
    """Setzt den polymorphen Kunden-Anker. Beide leer ("", 0) loest die Bindung."""
    _validate_customer(customer_cls or "", int(customer_id or 0))
    with session_for_tenant(_slug()) as s:
        obj = s.get(Process, int(process_id))
        if obj is None or obj.is_deleted:
            return {"error": f"process id={process_id} nicht gefunden"}
        obj.customer_cls = customer_cls or ""
        obj.customer_id = int(customer_id or 0)
        s.commit()
        s.refresh(obj)
        return _to_dict(obj)


@mcp.tool()
def archive_process(id: int) -> dict:
    """Soft-Delete eines Vorgangs (is_deleted=True)."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(Process, int(id))
        if obj is None:
            return {"error": f"process id={id} nicht gefunden"}
        obj.is_deleted = True
        s.commit()
        logger.info("process_archive id=%s", obj.id)
        return {"ok": True, "id": int(obj.id)}


@mcp.tool()
def allowed_status_values(process_id: int = 0) -> dict:
    """Liefert die aktuell erlaubten Status-Werte (Resolver-Sicht)."""
    slug = _slug()
    return {
        "allowed": _allowed_status(slug, process_id or None),
        "closed_values": sorted(_closed_status(slug)),
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    logger.info(
        "Starte wai-process-mcp auf Port %s via SSE (tenant=%s)", port, _slug()
    )
    mcp.run(transport="sse")
