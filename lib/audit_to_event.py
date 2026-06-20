"""Auto-Erzeugung fachlicher Events aus dem Change-Log — Plan 08.

Mechanik (Plan 08 Offene Frage 5, Option a):

    1. ``lib.audit._before_flush`` queued pending EntityChange-Eintraege
       in ``session.info["audit_change_log"]``.
    2. ``lib.audit._after_commit`` -> ``_drain()`` schreibt sie in
       ``logging_db.entity_change`` und legt einen Snapshot mit den frisch
       vergebenen IDs in ``session.info["audit_change_log_committed"]`` ab.
    3. Unser ``_after_commit_listener`` laeuft DANACH (Registrierungs-
       Reihenfolge garantiert) — er liest den Snapshot, prueft pro Eintrag
       gegen die Whitelist aus ``business_events.iter_auto_rules`` und
       schreibt pro Treffer ein ``BusinessEvent`` in die Tenant-DB.
       Idempotent ueber ``source_ref = "entity_change:<id>"``.

Wichtig: ``install_event_hooks()`` MUSS nach ``install_change_log_hooks()``
aufgerufen werden. Smoke verifiziert die Reihenfolge (case_listener_order).

V1 nimmt der Listener den Aktor des verursachenden EntityChange-Eintrags
1:1: ein Status-Wechsel via sales_support-MCP-Call landet als Event mit
``actor_type="ai"``, ``agent_name="sales_support"`` — die Brandkette bleibt
sichtbar. ``source="auto_change_log"`` markiert die Auto-Herkunft.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from lib.audit import COMMITTED_KEY
from lib.business_events import iter_auto_rules, render_title
from lib.db import session_for_tenant
from lib.logging import get_logger

log = get_logger(__name__)


def _build_events(snap: dict, rules: list[dict]) -> list[dict]:
    """Materialisiert pro passendem (Diff, Rule)-Paar einen Event-Stub."""
    out: list[dict] = []
    if snap.get("change_type") != "update":
        # V1: nur Field-Updates triggern Auto-Events. Status-Wechsel beim
        # Create eines Process landet als change_type="create" mit leerem
        # field_diffs (Plan 04 Konvention) — koennen wir nicht als
        # status_changed materialisieren.
        return out

    target_cls = snap.get("target_cls") or ""
    target_id = int(snap.get("target_id") or 0)
    if not target_cls or target_id <= 0:
        return out

    for diff in snap.get("field_diffs", []) or []:
        if not isinstance(diff, dict):
            continue
        field = diff.get("field") or ""
        if not field or diff.get("truncated"):
            # truncated-Diffs haben keine alten/neuen Werte — wir koennen
            # weder Titel formatieren noch data sinnvoll fuellen.
            continue
        for rule in rules:
            if rule.get("field") != field:
                continue
            old = diff.get("old")
            new = diff.get("new")
            title = render_title(
                rule.get("title_template") or "",
                old=old,
                new=new,
            )
            out.append({
                "target_cls": target_cls,
                "target_id": target_id,
                "event_type": rule.get("event_type") or "field_changed",
                "title": title,
                "body": "",
                "actor_type": snap.get("actor_type") or "system",
                "actor_id": int(snap.get("actor_id") or 0),
                "agent_name": snap.get("agent_name") or "",
                "trace_uid": snap.get("trace_uid") or "",
                "source": "auto_change_log",
                "source_ref": f"entity_change:{snap.get('id')}",
                "data": {"old": old, "new": new, "field": field},
            })
    return out


def _resolve_tenant_slug(snapshots: list[dict]) -> str | None:
    """Plan 04 setzt tenant_id auf jedem EntityChange-Eintrag — wir nehmen
    den ersten nicht-leeren Wert. In der Praxis schreibt ein Commit immer
    in genau eine Tenant-DB.
    """
    for snap in snapshots:
        tid = (snap.get("tenant_id") or "").strip()
        if tid:
            return tid
    return None


def _after_commit_listener(session: Session) -> None:
    snapshots: list[dict] | None = session.info.pop(COMMITTED_KEY, None)
    if not snapshots:
        return

    tenant_slug = _resolve_tenant_slug(snapshots)
    if not tenant_slug:
        # z.B. Setting-Mini-Audit schreibt mit tenant_id="" — keine Tenant-
        # spezifischen Events generierbar. Plan 08 V1: still ignorieren.
        log.debug(
            "audit_to_event: tenant_id leer auf allen snapshots — skip (n=%d)",
            len(snapshots),
        )
        return

    pending: list[dict] = []
    for snap in snapshots:
        target_cls = snap.get("target_cls") or ""
        rules = iter_auto_rules(target_cls, tenant=tenant_slug)
        if not rules:
            continue
        pending.extend(_build_events(snap, rules))

    if not pending:
        return

    try:
        with session_for_tenant(tenant_slug) as fresh:
            from lib.entities.tenant.business_event import BusinessEvent  # lazy
            now = datetime.now(timezone.utc)
            written = 0
            for stub in pending:
                # Idempotenz: pro source_ref nur ein Event. Falls Hook
                # versehentlich zweimal feuert (Re-Drain, Replay), ueberspringen.
                existing = fresh.execute(
                    select(BusinessEvent.id)
                    .where(BusinessEvent.source == stub["source"])
                    .where(BusinessEvent.source_ref == stub["source_ref"])
                    .where(BusinessEvent.is_deleted.is_(False))
                    .limit(1)
                ).first()
                if existing:
                    continue
                fresh.add(BusinessEvent(
                    happened_at=now,
                    event_type=stub["event_type"],
                    title=stub["title"],
                    body=stub["body"],
                    target_cls=stub["target_cls"],
                    target_id=stub["target_id"],
                    actor_type=stub["actor_type"],
                    actor_id=stub["actor_id"],
                    agent_name=stub["agent_name"],
                    trace_uid=stub["trace_uid"],
                    source=stub["source"],
                    source_ref=stub["source_ref"],
                    data=stub["data"],
                ))
                written += 1
            fresh.commit()
        if written:
            log.info(
                "audit_to_event: %d Auto-Event(s) geschrieben (tenant=%s)",
                written, tenant_slug,
            )
    except Exception:
        log.warning(
            "audit_to_event: drain fehlgeschlagen (tenant=%s, n=%d)",
            tenant_slug, len(pending), exc_info=True,
        )


_listeners_registered = False


def install_event_hooks() -> None:
    """Registriert den Auto-Event-Listener idempotent.

    MUSS NACH ``lib.audit.install_change_log_hooks()`` aufgerufen werden —
    SQLAlchemy ruft after_commit-Listener in Registrierungsreihenfolge,
    der Snapshot kommt aus dem Change-Log-Drain.
    """
    global _listeners_registered
    if _listeners_registered:
        return
    event.listen(Session, "after_commit", _after_commit_listener)
    _listeners_registered = True
    log.info("audit_to_event hooks registriert (Plan 08)")
