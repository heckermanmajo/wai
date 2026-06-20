"""Fachliche Events — Helper-Modul (Plan 08).

Schmale API ueber der ``BusinessEvent``-Entity:

    log_event(target_cls, target_id, event_type, ...) -> int
        Schreibt ein Event in der Tenant-Session. Fuellt actor_type /
        actor_id / agent_name / trace_uid aus ``lib.tenant_context``.

    iter_auto_rules(target_cls, tenant=None) -> list[dict]
        Liefert die Auto-Erzeuger-Whitelist aus dem Settings-Resolver
        (``events.auto_rules.<target_cls>``). Default in PLATFORM_DEFAULTS.

V1-Konvention der ``event_type``-Strings (kein Validator, Plan 08
Offene Frage 6):

    status_changed       — Auto, aus Process-Status-Wechsel
    manual_entry         — Default fuer log_event ohne expliziten Typ
    call_logged          — manuell, "Kunde angerufen"
    mail_sent            — manuell, "Mail rausgegangen"
    meeting_scheduled    — manuell, "Termin vereinbart"
    note_added           — manuell, "Notiz angeheftet"

Erweiterungen frei: V1 ist es Doku-Konvention, kein Schema-Validator.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lib.db import session_for_tenant
from lib.entities.tenant.business_event import BusinessEvent
from lib.logging import get_logger
from lib.settings import resolve as settings_resolve
from lib.tenant_context import (
    get_actor,
    get_trace_uid,
    get_user,
    require_tenant,
)

log = get_logger(__name__)

# V1-Konventions-Liste (siehe Modul-Docstring). KEIN Validator — Doku.
BUSINESS_EVENT_TYPES: tuple[str, ...] = (
    "status_changed",
    "manual_entry",
    "call_logged",
    "mail_sent",
    "meeting_scheduled",
    "note_added",
)


def log_event(
    *,
    target_cls: str,
    target_id: int,
    event_type: str,
    title: str = "",
    body: str = "",
    happened_at: datetime | None = None,
    data: dict | None = None,
    source: str = "manual",
    source_ref: str = "",
    tenant_slug: str | None = None,
) -> int:
    """Schreibt ein BusinessEvent in der Tenant-DB.

    Aktor-Felder (actor_type, actor_id, agent_name, trace_uid) werden aus
    den ``tenant_context``-ContextVars gefuellt. Anker (target_cls + target_id)
    ist Pflicht (Plan 08 Offene Frage 4: keine "globalen" Events in V1).
    """
    target_cls = (target_cls or "").strip()
    if not target_cls or int(target_id or 0) <= 0:
        raise ValueError(
            "BusinessEvent braucht target_cls und target_id > 0 — "
            "globale Events sind in V1 nicht vorgesehen (Plan 08 Offene Frage 4)."
        )
    event_type = (event_type or "manual_entry").strip()

    slug = tenant_slug or require_tenant()
    actor_type, agent_name = get_actor()
    when = happened_at or datetime.now(timezone.utc)

    with session_for_tenant(slug) as s:
        obj = BusinessEvent(
            happened_at=when,
            event_type=event_type,
            title=title or "",
            body=body or "",
            target_cls=target_cls,
            target_id=int(target_id),
            actor_type=actor_type or "system",
            actor_id=int(get_user() or 0),
            agent_name=agent_name or "",
            trace_uid=get_trace_uid() or "",
            source=source or "manual",
            source_ref=source_ref or "",
            data=data or {},
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        new_id = int(obj.id)
        log.info(
            "business_event_log id=%s type=%s target=%s#%s source=%s",
            new_id, event_type, target_cls, target_id, source,
        )
        return new_id


def iter_auto_rules(target_cls: str, tenant: str | None = None) -> list[dict]:
    """Lade die Whitelist fuer Auto-Event-Erzeugung aus dem Settings-Resolver.

    Key-Konvention: ``events.auto_rules.<target_cls>``. PLATFORM_DEFAULTS
    enthaelt den V1-Default; pro Tenant via ``set_value(scope="tenant", ...)``
    ueberschreibbar — gleicher Mechanismus wie ``process.status.allowed_values``.
    Plan 08 Offene Frage 2: keine eigene Tabelle.
    """
    key = f"events.auto_rules.{target_cls}"
    try:
        val = settings_resolve(
            key,
            tenant=tenant or None,
            entity_cls=target_cls or None,
        )
    except KeyError:
        return []
    if not isinstance(val, list):
        return []
    out: list[dict] = []
    for entry in val:
        if isinstance(entry, dict) and entry.get("field"):
            out.append(entry)
    return out


def render_title(template: str, *, old: Any = None, new: Any = None) -> str:
    """Default-Renderer fuer ``title_template`` der Auto-Rules.

    Format-Args: ``old`` / ``new`` aus dem Change-Log-Diff. Wenn die
    Format-Operation scheitert (unbekannter Platzhalter), nehmen wir das
    Template woertlich — der Listener soll niemals an einem schlecht
    konfigurierten Setting crashen.
    """
    tpl = template or ""
    if not tpl:
        return ""
    try:
        return tpl.format(old=old if old is not None else "", new=new if new is not None else "")
    except Exception:
        log.warning("auto_event title_template render fehlgeschlagen: %r", tpl)
        return tpl
