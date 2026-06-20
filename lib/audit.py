"""Change-Log — automatischer Audit-Trail pro Feld-Aenderung (Plan 04).

Mechanik:
    - ``install_change_log_hooks()`` registriert SQLAlchemy-Event-Listener
      auf der ``Session``-Klasse.
    - ``before_flush``: inspiziert ``session.new``, ``session.dirty``,
      ``session.deleted``. Pro betroffene Row baut er ein ``pending_change``
      Dict in ``session.info`` (NICHT in DB!).
    - ``after_commit``: liest die Pending-Liste und schreibt sie als
      Batch in ``logging_db.entity_change`` ueber eine **eigene** Session.

Damit landen Audit-Eintraege erst, wenn die eigentliche Aenderung sicher
committet ist — und wir koennen keine Audit-Loops bei Roll-Back kriegen.

Opt-Out per Klassenattribut ``__change_log__ = False`` (Standard ist True
fuer alle BaseMixin-Erben):
    - ``SemanticSnippet``  — schreibintensiv, kein Audit-Wert.
    - ``AiMessage``, ``AiToolCall`` — Telemetrie, keine Fachlichkeit.
    - ``Setting``         — eigener Mini-Audit-Pfad in ``lib/settings.py``.
    - ``EntityChange``    — Audit-Tabelle selbst (Hen-Ei).

Nicht-ORM-Pfade: Raw-SQL-Bulk-Updates umgehen den Hook. Das ist Absicht
— wer Audit-Coverage braucht, faehrt ORM. Plan 04 Offene Frage 5.
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any, Iterable

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from lib.db import session_for_logging
from lib.logging import get_logger
from lib.polymorphic import alias_for
from lib.tenant_context import get_actor, get_tenant, get_trace_uid, get_user

log = get_logger(__name__)


CHANGE_LOG_FIELD_MAX_BYTES = 4096

_OUTBOX_KEY = "audit_change_log"

# ContextVar fuer optionale, vom Agent gesetzte Summary fuer den NAECHSTEN
# logischen Save. Plan 04 — Setting-Override fuer "Beschreibung um …
# ergaenzt" o.Ae. Wirkt einmalig: nach dem after_commit-Flush wieder leer.
_change_summary_override: ContextVar[str | None] = ContextVar(
    "wai_change_summary_override", default=None
)


def set_change_summary(summary: str | None) -> None:
    """Optional: setzt einen sprechenden Summary fuer den naechsten Save.

    Wird vom Hook bevorzugt, statt der Default-Vorlage. Wirkt nur einmalig
    pro Session-Flush.
    """
    _change_summary_override.set(summary or None)


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------


def _utf8_len(v: Any) -> int:
    if v is None:
        return 0
    if isinstance(v, str):
        return len(v.encode("utf-8"))
    if isinstance(v, (bytes, bytearray)):
        return len(v)
    try:
        return len(json.dumps(v, default=str).encode("utf-8"))
    except Exception:
        return len(str(v).encode("utf-8"))


def _truncate_diff(field: str, old: Any, new: Any) -> dict:
    old_len = _utf8_len(old)
    new_len = _utf8_len(new)
    if old_len > CHANGE_LOG_FIELD_MAX_BYTES or new_len > CHANGE_LOG_FIELD_MAX_BYTES:
        return {
            "field": field,
            "old": None,
            "new": None,
            "truncated": True,
            "old_len": old_len,
            "new_len": new_len,
        }
    return {"field": field, "old": _jsonable(old), "new": _jsonable(new)}


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (bytes, bytearray)):
        return f"<{len(v)} bytes>"
    try:
        json.dumps(v)
        return v
    except Exception:
        return str(v)


# ---------------------------------------------------------------------------
# Inspection: feld-diffs aus SQLAlchemy
# ---------------------------------------------------------------------------


_EXCLUDED_COLUMN_NAMES = {"updated_at", "created_at"}


def _is_opted_out(target: Any) -> bool:
    return bool(getattr(type(target), "__change_log__", True) is False)


def _resolve_target_cls(target: Any) -> str:
    cls = type(target)
    alias = alias_for(cls)
    if alias:
        return alias
    # Fallback: <modul>.<Klasse> lowercase. Verhindert leere Audit-Eintraege fuer
    # nicht-registrierte Tabellen (Admin-Entities werden i.d.R. nicht polymorph
    # registriert).
    mod = cls.__module__.split(".")[-1]
    return f"{mod}.{cls.__name__.lower()}"


def _detect_field_diffs(target: Any) -> tuple[list[dict], bool]:
    """Liefert (diffs, is_soft_delete). diffs sind bereits truncated."""
    diffs: list[dict] = []
    is_soft_delete = False
    state = inspect(target)
    for attr in state.attrs:
        name = attr.key
        if name in _EXCLUDED_COLUMN_NAMES:
            continue
        hist = attr.history
        if not hist.has_changes():
            continue
        # added/deleted koennen mehrere Werte enthalten — wir nehmen jeweils [0]
        old = hist.deleted[0] if hist.deleted else None
        new = hist.added[0] if hist.added else getattr(target, name, None)
        if old == new:
            continue
        if name == "is_deleted" and old is False and new is True:
            is_soft_delete = True
        diffs.append(_truncate_diff(name, old, new))
    return diffs, is_soft_delete


def _build_summary(target: Any, change_type: str, diffs: list[dict]) -> str:
    override = _change_summary_override.get()
    if override:
        _change_summary_override.set(None)
        return override
    if change_type == "create":
        title = getattr(target, "title", None) or getattr(target, "name", None) or ""
        return "Erstellt" + (f" ({title})" if title else "")
    if change_type in ("delete", "soft_delete"):
        return "Geloescht"
    if change_type == "update":
        field_names = [d.get("field", "?") for d in diffs]
        n = len(field_names)
        if n == 0:
            return "Aktualisiert"
        if n <= 3:
            return f"{n} Feld(er) geaendert: {', '.join(field_names)}"
        return f"{n} Felder geaendert: {', '.join(field_names[:3])} …"
    return change_type


def _build_pending(
    target: Any,
    change_type: str,
    diffs: list[dict],
) -> dict | None:
    if _is_opted_out(target):
        return None
    tid = getattr(target, "id", None)
    if not tid:
        # neu eingefuegte Rows ohne ID koennen wir hier nicht adressieren —
        # die behandeln wir gesondert nach dem flush() (siehe _before_flush).
        return None
    target_cls = _resolve_target_cls(target)
    actor_type, agent_name = get_actor()
    return {
        "tenant_id": get_tenant() or "",
        "target_cls": target_cls,
        "target_id": int(tid),
        "change_type": change_type,
        "actor_type": actor_type,
        "actor_id": int(get_user() or 0),
        "agent_name": agent_name,
        "trace_uid": get_trace_uid() or "",
        "field_diffs": diffs,
        "summary": _build_summary(target, change_type, diffs),
    }


# ---------------------------------------------------------------------------
# Outbox
# ---------------------------------------------------------------------------


def _queue(session: Session, entry: dict) -> None:
    bag: list[dict] = session.info.setdefault(_OUTBOX_KEY, [])
    bag.append(entry)


def _drain(session: Session) -> None:
    bag: list[dict] | None = session.info.pop(_OUTBOX_KEY, None)
    if not bag:
        return
    try:
        with session_for_logging() as fresh:
            from lib.entities.logging.entity_change import EntityChange  # lazy
            for e in bag:
                fresh.add(EntityChange(**e))
            fresh.commit()
    except Exception:
        log.warning(
            "audit_drain_failed (n=%d) — Audit-Eintraege verworfen",
            len(bag), exc_info=True,
        )


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def _before_flush(session: Session, flush_context, instances) -> None:
    # Update: dirty enthaelt veraenderte Rows mit alten/neuen Werten
    for obj in list(session.dirty):
        if _is_opted_out(obj):
            continue
        diffs, soft_delete = _detect_field_diffs(obj)
        if not diffs:
            continue
        change_type = "soft_delete" if soft_delete else "update"
        entry = _build_pending(obj, change_type, diffs)
        if entry:
            _queue(session, entry)
    # Hard-Delete
    for obj in list(session.deleted):
        if _is_opted_out(obj):
            continue
        entry = _build_pending(obj, "delete", [])
        if entry:
            _queue(session, entry)
    # Create: die Rows haben ggf. noch keine ID. Wir markieren sie und holen
    # die IDs in _after_flush nach.
    pending_new = session.info.setdefault("audit_pending_new", [])
    for obj in list(session.new):
        if _is_opted_out(obj):
            continue
        # initialer Diff = alle gesetzten, nicht-None-Felder (=neuer Zustand)
        pending_new.append(obj)


def _after_flush(session: Session, flush_context) -> None:
    pending_new: list = session.info.pop("audit_pending_new", []) or []
    for obj in pending_new:
        if _is_opted_out(obj):
            continue
        # Nach flush() hat obj.id einen Wert. field_diffs bleibt leer fuer
        # create — Plan 04 sagt explizit "leer bei create/delete".
        entry = _build_pending(obj, "create", [])
        if entry:
            _queue(session, entry)


def _after_commit(session: Session) -> None:
    _drain(session)


def _after_rollback(session: Session) -> None:
    session.info.pop(_OUTBOX_KEY, None)
    session.info.pop("audit_pending_new", None)


_listeners_registered = False


def install_change_log_hooks() -> None:
    """Registriert die SQLAlchemy-Event-Listener idempotent."""
    global _listeners_registered
    if _listeners_registered:
        return
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "after_flush", _after_flush)
    event.listen(Session, "after_commit", _after_commit)
    event.listen(Session, "after_rollback", _after_rollback)
    _listeners_registered = True
    log.info("change_log_hooks registriert")


# ---------------------------------------------------------------------------
# Setting-Mini-Audit (umgeht den ORM-Hook)
# ---------------------------------------------------------------------------


def write_setting_change_log(
    *,
    tenant_id: str,
    target_cls: str,
    target_id: int,
    change_type: str,
    scope: str,
    scope_ref: str,
    entity_cls: str,
    entity_id: int,
    key: str,
    old: Any,
    new: Any,
    set_by: int,
    summary: str | None = None,
) -> None:
    """Direkt-Schreibpfad fuer Setting-Aenderungen.

    Setting selbst hat ``__change_log__ = False`` (siehe oben). Diese
    Funktion schreibt einen Audit-Eintrag im selben Format wie der ORM-Hook,
    aber in einer eigenen Logging-Session. Plan 04 Offene Frage 4.
    """
    actor_type, agent_name = get_actor()
    diff = _truncate_diff("value", old, new)
    # zusaetzlich Setting-Schicht-Info ins Diff stopfen — laesst sich im UI
    # als Header anzeigen ("ai.changes.mode auf tenant=demo gesetzt").
    diff["scope"] = scope
    diff["scope_ref"] = scope_ref
    diff["entity_cls"] = entity_cls
    diff["entity_id"] = entity_id
    diff["key"] = key
    diff["set_by"] = set_by
    if not summary:
        summary = f"Setting {key} {change_type} (scope={scope})"
    try:
        with session_for_logging() as s:
            from lib.entities.logging.entity_change import EntityChange  # lazy
            s.add(EntityChange(
                tenant_id=tenant_id or "",
                target_cls=target_cls,
                target_id=int(target_id),
                change_type=change_type,
                actor_type=actor_type,
                actor_id=int(get_user() or 0),
                agent_name=agent_name,
                trace_uid=get_trace_uid() or "",
                field_diffs=[diff],
                summary=summary,
            ))
            s.commit()
    except Exception:
        log.warning("setting_audit_write_failed key=%s", key, exc_info=True)


# ---------------------------------------------------------------------------
# Read-API fuer Verlaufs-Tab
# ---------------------------------------------------------------------------


def list_entity_changes(
    *,
    tenant_id: str,
    target_cls: str,
    target_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Liefert die letzten Audit-Eintraege zu einer Entity (Verlaufs-Tab)."""
    from sqlalchemy import select  # lazy
    from lib.entities.logging.entity_change import EntityChange  # lazy
    out: list[dict] = []
    with session_for_logging() as s:
        rows = s.execute(
            select(EntityChange)
            .where(EntityChange.tenant_id == tenant_id)
            .where(EntityChange.target_cls == target_cls)
            .where(EntityChange.target_id == int(target_id))
            .where(EntityChange.is_deleted.is_(False))
            .order_by(EntityChange.created_at.desc())
            .limit(int(limit)).offset(int(offset))
        ).scalars().all()
        for r in rows:
            out.append({
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "tenant_id": r.tenant_id,
                "target_cls": r.target_cls,
                "target_id": r.target_id,
                "change_type": r.change_type,
                "actor_type": r.actor_type,
                "actor_id": r.actor_id,
                "agent_name": r.agent_name,
                "trace_uid": r.trace_uid,
                "field_diffs": r.field_diffs,
                "summary": r.summary,
            })
    return out


def opted_out_classes() -> Iterable[str]:
    """Hilfs-Listing fuer Debug — welche Entity-Klassen sind opt-out."""
    return ("SemanticSnippet", "AiMessage", "AiToolCall", "Setting", "EntityChange")
