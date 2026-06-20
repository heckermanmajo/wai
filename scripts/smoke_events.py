"""Smoke-Skript: Plan 08 (Fachliche Events) Mindest-Cases.

Laeuft als ausfuehrbares Skript gegen einen LAUFENDEN Stack (Postgres
muss erreichbar sein, Tenant ``demo`` muss bis ``tenant_0011`` migriert
sein). Deckt die Plan-08-Mindest-Cases ab, ohne pytest-Setup einzufuehren
— analog zu ``scripts/smoke_process.py``.

Aufruf:
    docker compose exec -T gateway python scripts/smoke_events.py
    # oder lokal mit gesetzten ENV-Vars:
    python scripts/smoke_events.py [--tenant demo]

Bei Fehler exited der Prozess mit Code 1; pro Case ein ``[ok]``-Output.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import event as sa_event, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from lib.audit import install_change_log_hooks  # noqa: E402
from lib.audit_to_event import install_event_hooks  # noqa: E402
from lib.business_events import log_event  # noqa: E402
from lib.db import session_for_logging, session_for_tenant  # noqa: E402
from lib.entities.tenant import BusinessEvent, Process, SemanticFassade  # noqa: E402
from lib.tenant_context import set_actor, set_tenant, set_trace_uid  # noqa: E402

SMOKE_PREFIX = "Smoke-Test:"


class SmokeFail(Exception):
    """Markiert ein fehlgeschlagenes Smoke-Case."""


def _ok(case: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"[ok] {case}{suffix}", flush=True)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise SmokeFail(msg)


def _wait_for_business_event(
    slug: str,
    *,
    source_ref: str,
    timeout_s: float = 5.0,
) -> BusinessEvent | None:
    """Auto-Event entsteht im after_commit-Drain in eigener Session — pollen."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with session_for_tenant(slug) as s:
            row = s.execute(
                select(BusinessEvent)
                .where(BusinessEvent.source == "auto_change_log")
                .where(BusinessEvent.source_ref == source_ref)
                .where(BusinessEvent.is_deleted.is_(False))
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                return row
        time.sleep(0.2)
    return None


def _latest_entity_change_id(target_cls: str, target_id: int) -> int | None:
    from lib.entities.logging.entity_change import EntityChange  # lazy

    with session_for_logging() as s:
        row = s.execute(
            select(EntityChange.id, EntityChange.change_type)
            .where(EntityChange.target_cls == target_cls)
            .where(EntityChange.target_id == int(target_id))
            .order_by(EntityChange.id.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        return int(row[0])


def _create_smoke_process(slug: str) -> int:
    set_tenant(slug)
    set_actor("ai", "smoke_events")
    with session_for_tenant(slug) as s:
        obj = Process(
            name=f"{SMOKE_PREFIX} Events-Anker",
            description="Process fuer Plan-08-Smoke.",
            kind="smoke_events",
            status="neu",
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        return int(obj.id)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def case_schema_defaults(slug: str) -> None:
    """Tabelle event existiert, Default-Werte greifen."""
    set_tenant(slug)
    pid = _create_smoke_process(slug)
    with session_for_tenant(slug) as s:
        ev = BusinessEvent(
            happened_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
            event_type="manual_entry",
            target_cls="core.process",
            target_id=pid,
        )
        s.add(ev)
        s.commit()
        s.refresh(ev)
        _assert(ev.id > 0, "BusinessEvent bekam keine id")
        _assert(ev.title == "", f"title default falsch: {ev.title!r}")
        _assert(ev.body == "", f"body default falsch: {ev.body!r}")
        _assert(ev.actor_type == "system", f"actor_type default falsch: {ev.actor_type!r}")
        _assert(ev.source == "manual", f"source default falsch: {ev.source!r}")
        _assert(ev.data == {}, f"data default falsch: {ev.data!r}")
        # cleanup nicht noetig — Smoke laeuft idempotent gegen demo
    _ok("schema + defaults")


def case_manual_event_actor_from_context(slug: str) -> int:
    """log_event fuellt actor_type/agent_name aus tenant_context."""
    set_tenant(slug)
    set_actor("ai", "smoke_events")
    set_trace_uid("")  # bewusst leer fuer diesen Case
    pid = _create_smoke_process(slug)
    new_id = log_event(
        target_cls="core.process",
        target_id=pid,
        event_type="call_logged",
        title="Anruf von Kunde",
        body="Kunde meldet Defekt an Geraet X.",
        data={"phone": "0800-12345"},
    )
    with session_for_tenant(slug) as s:
        ev = s.get(BusinessEvent, new_id)
        _assert(ev is not None, "BusinessEvent nicht wiedergefunden")
        _assert(ev.actor_type == "ai", f"actor_type aus context falsch: {ev.actor_type!r}")
        _assert(ev.agent_name == "smoke_events", f"agent_name falsch: {ev.agent_name!r}")
        _assert(ev.trace_uid == "", f"trace_uid sollte leer sein: {ev.trace_uid!r}")
        _assert(ev.event_type == "call_logged", f"event_type: {ev.event_type!r}")
        _assert(ev.data.get("phone") == "0800-12345", f"data: {ev.data!r}")
    _ok("manual log_event + aktor aus context", f"event_id={new_id}")
    return pid


def case_trace_uid_bridge(slug: str, process_id: int) -> None:
    """trace_uid aus tenant_context landet im Event."""
    set_tenant(slug)
    set_actor("ai", "smoke_events")
    test_trace = "trace_smoke_events_42"
    set_trace_uid(test_trace)
    new_id = log_event(
        target_cls="core.process",
        target_id=process_id,
        event_type="mail_sent",
        title="Statusupdate an Kunde",
    )
    with session_for_tenant(slug) as s:
        ev = s.get(BusinessEvent, new_id)
        _assert(ev is not None, "BusinessEvent nicht gefunden")
        _assert(ev.trace_uid == test_trace, f"trace_uid bridge falsch: {ev.trace_uid!r}")
    # reset
    set_trace_uid("")
    _ok("trace_uid bridge -> logging.trace", f"trace_uid={test_trace}")


def case_auto_event_from_status_change(slug: str) -> tuple[int, int]:
    """set_status(pid, ...) triggert genau einen Auto-Event mit source_ref."""
    set_tenant(slug)
    set_actor("ai", "smoke_events")
    pid = _create_smoke_process(slug)

    os.environ.setdefault("WAI_TENANT_SLUG_DEFAULT", slug)
    from mcp_servers.process_mcp.server import set_status

    res = set_status(pid, "in_arbeit")
    _assert("error" not in res, f"set_status fehlgeschlagen: {res}")
    _assert(res["status"] == "in_arbeit", f"status: {res['status']}")

    # Audit-Drain ist after_commit; gib der zweiten Session etwas Zeit.
    time.sleep(0.3)
    change_id = _latest_entity_change_id("core.process", pid)
    _assert(change_id is not None, "kein EntityChange-Eintrag nach Status-Wechsel")
    source_ref = f"entity_change:{change_id}"

    auto = _wait_for_business_event(slug, source_ref=source_ref)
    _assert(auto is not None, f"kein BusinessEvent mit source_ref={source_ref}")
    _assert(
        auto.event_type == "status_changed",
        f"event_type: {auto.event_type!r}",
    )
    _assert(auto.source == "auto_change_log", f"source: {auto.source!r}")
    _assert(auto.target_cls == "core.process", f"target_cls: {auto.target_cls!r}")
    _assert(auto.target_id == pid, f"target_id: {auto.target_id}")
    _assert(
        auto.actor_type == "ai" and auto.agent_name == "smoke_events",
        f"actor uebernommen aus EntityChange: {auto.actor_type}/{auto.agent_name}",
    )
    _assert(
        auto.data.get("old") == "neu" and auto.data.get("new") == "in_arbeit",
        f"data old/new: {auto.data!r}",
    )
    title = auto.title or ""
    _assert("neu" in title and "in_arbeit" in title, f"title template: {title!r}")

    # Idempotenz: zweiter Set auf den GLEICHEN Status erzeugt KEINEN
    # weiteren Auto-Event (es entsteht auch kein EntityChange, weil kein Diff).
    res2 = set_status(pid, "in_arbeit")
    _assert("error" not in res2, f"set_status nochmal fehlgeschlagen: {res2}")
    time.sleep(0.2)
    with session_for_tenant(slug) as s:
        cnt = s.execute(
            select(BusinessEvent.id)
            .where(BusinessEvent.target_cls == "core.process")
            .where(BusinessEvent.target_id == pid)
            .where(BusinessEvent.event_type == "status_changed")
            .where(BusinessEvent.is_deleted.is_(False))
        ).all()
        _assert(len(cnt) == 1, f"erwartet 1 Auto-Event, gefunden: {len(cnt)}")

    _ok("auto-event aus status_changed + idempotenz", f"process_id={pid} ce_id={change_id}")
    return pid, int(auto.id)


def case_selective_whitelist(slug: str, process_id: int) -> None:
    """Update auf description erzeugt EntityChange, aber KEINEN Auto-Event."""
    set_tenant(slug)
    set_actor("ai", "smoke_events")

    before_count = _count_events_for(slug, process_id)
    with session_for_tenant(slug) as s:
        p = s.get(Process, process_id)
        p.description = (p.description or "") + "\n\nNachtrag fuer Whitelist-Smoke."
        s.commit()
    time.sleep(0.3)

    after_count = _count_events_for(slug, process_id)
    _assert(
        after_count == before_count,
        f"description-Update erzeugte unerwartet Auto-Event "
        f"(before={before_count}, after={after_count})",
    )

    # Zur Gegenprobe: der EntityChange existiert.
    last_id = _latest_entity_change_id("core.process", process_id)
    _assert(last_id is not None, "EntityChange fuer description-Update fehlt")
    _ok("whitelist selektiv (description -> kein auto-event)")


def case_polymorph_filter(slug: str, process_id: int) -> None:
    """event_list filtert chronologisch nach target_cls/target_id."""
    os.environ.setdefault("WAI_TENANT_SLUG_DEFAULT", slug)
    from mcp_servers.events_mcp.server import event_list

    rows = event_list(target_cls="core.process", target_id=process_id, limit=10)
    _assert(isinstance(rows, list) and len(rows) >= 1, f"event_list leer: {rows!r}")
    for r in rows:
        _assert(r["target_cls"] == "core.process", f"falscher anker: {r}")
        _assert(r["target_id"] == process_id, f"falscher anker-id: {r}")
    # absteigend nach happened_at
    times = [r["happened_at"] for r in rows]
    _assert(times == sorted(times, reverse=True), "happened_at nicht desc")
    _ok("event_list polymorph + chronologisch", f"n={len(rows)}")


def case_soft_delete_no_change_log(slug: str, event_id: int) -> None:
    """event_delete(id) setzt is_deleted=True und schreibt KEINEN Change-Log
    (BusinessEvent hat __change_log__ = False — Plan 08 Offene Frage 8).
    """
    os.environ.setdefault("WAI_TENANT_SLUG_DEFAULT", slug)
    from mcp_servers.events_mcp.server import event_delete, event_list

    before_id = _latest_entity_change_id("core.event", event_id)
    res = event_delete(event_id)
    _assert(res.get("ok") is True, f"event_delete: {res}")

    with session_for_tenant(slug) as s:
        ev = s.get(BusinessEvent, event_id)
        _assert(ev is not None and ev.is_deleted, "is_deleted nicht gesetzt")

    listed = event_list(include_deleted=False, limit=200)
    _assert(
        all(r["id"] != event_id for r in listed),
        f"soft-geloeschtes Event taucht in event_list auf: id={event_id}",
    )

    time.sleep(0.2)
    after_id = _latest_entity_change_id("core.event", event_id)
    _assert(
        after_id == before_id,
        f"BusinessEvent-Soft-Delete schrieb Change-Log "
        f"(before={before_id}, after={after_id}) — __change_log__-Flag wirkt nicht",
    )
    _ok("soft-delete + kein change-log fuer events")


def case_semantic_fassade(slug: str) -> None:
    """Nach log_event existiert eine SemanticFassade fuer das Event."""
    set_tenant(slug)
    set_actor("ai", "smoke_events")
    set_trace_uid("")
    pid = _create_smoke_process(slug)
    new_id = log_event(
        target_cls="core.process",
        target_id=pid,
        event_type="meeting_scheduled",
        title=f"{SMOKE_PREFIX} Termin in KW42",
        body="Vor-Ort-Termin beim Kunden vereinbart.",
    )

    deadline = time.monotonic() + 5.0
    fassade = None
    while time.monotonic() < deadline:
        with session_for_tenant(slug) as s:
            fassade = s.execute(
                select(SemanticFassade)
                .where(SemanticFassade.entity_class == "core.event")
                .where(SemanticFassade.entity_id == int(new_id))
                .where(SemanticFassade.is_deleted.is_(False))
                .limit(1)
            ).scalar_one_or_none()
            if fassade is not None:
                break
        time.sleep(0.2)
    _assert(fassade is not None, "SemanticFassade fuer BusinessEvent fehlt")
    _ok("semantic fassade fuer business_event", f"event_id={new_id}")


def case_mcp_tool_smoke(slug: str) -> None:
    """Happy-Path event_log -> event_get -> event_list -> event_delete."""
    os.environ.setdefault("WAI_TENANT_SLUG_DEFAULT", slug)
    set_tenant(slug)
    set_actor("ai", "smoke_events")
    from mcp_servers.events_mcp.server import (
        event_delete,
        event_get,
        event_list,
        event_log,
        manifest,
    )

    m = manifest()
    _assert(m.get("kind") == "tool", f"manifest.kind={m.get('kind')}")
    _assert("core.event" in (m.get("entities") or []), "entities fehlt core.event")
    _assert(
        "status_changed" in (m.get("event_type_conventions") or []),
        "event_type_conventions fehlt 'status_changed'",
    )

    pid = _create_smoke_process(slug)

    # Anker-Pflicht (Plan 08 Offene Frage 4)
    bad = event_log(target_cls="", target_id=0, event_type="manual_entry")
    _assert("error" in bad, "MCP haette leeren Anker ablehnen muessen")

    created = event_log(
        target_cls="core.process",
        target_id=pid,
        event_type="note_added",
        title="MCP-Smoke",
        body="Happy-Path",
    )
    _assert("error" not in created, f"event_log: {created}")
    eid = int(created["id"])

    got = event_get(eid)
    _assert(got["id"] == eid, "event_get inkonsistent")
    _assert(got["event_type"] == "note_added", f"event_type: {got['event_type']!r}")

    listing = event_list(target_cls="core.process", target_id=pid, limit=20)
    _assert(any(r["id"] == eid for r in listing), "event_list findet event nicht")

    arch = event_delete(eid)
    _assert(arch.get("ok") is True, f"event_delete: {arch}")
    after = event_get(eid)
    _assert(after.get("is_deleted") is True, f"event nach delete: {after}")

    _ok("mcp tools happy path", f"event_id={eid}")


def case_listener_order(slug: str) -> None:
    """SQLAlchemy ruft after_commit-Listener in Registrierungsreihenfolge —
    Plan 08 Offene Frage 5 verlangt explizit, dass unser audit_to_event-
    Listener NACH audit._after_commit registriert wurde. Wir verifizieren
    das ueber den private Listener-Manager.
    """
    from lib.audit import _after_commit as audit_after_commit
    from lib.audit_to_event import _after_commit_listener as auto_after_commit

    listeners = sa_event.contains(Session, "after_commit", audit_after_commit)
    _assert(listeners, "audit._after_commit nicht registriert")
    listeners2 = sa_event.contains(Session, "after_commit", auto_after_commit)
    _assert(listeners2, "audit_to_event._after_commit_listener nicht registriert")

    # Reihenfolge: ich erzeuge einen kontrollierten Commit und beobachte,
    # dass der COMMITTED_KEY zuerst vom Drain gesetzt UND von unserem
    # Listener konsumiert wird (sonst waere er nach dem Commit nicht weg).
    from lib.audit import COMMITTED_KEY
    set_tenant(slug)
    set_actor("ai", "smoke_events")
    pid = _create_smoke_process(slug)
    with session_for_tenant(slug) as s:
        p = s.get(Process, pid)
        # Status-Wechsel ist whitelisted -> triggert audit + auto_event
        p.status = "in_arbeit"
        s.commit()
        # nach commit muss der KEY weg sein (vom auto-Listener konsumiert)
        _assert(
            COMMITTED_KEY not in s.info,
            "COMMITTED_KEY blieb in session.info — auto-Listener lief NICHT nach drain",
        )
    _ok("after_commit reihenfolge: drain -> auto-event")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_events_for(slug: str, process_id: int) -> int:
    with session_for_tenant(slug) as s:
        rows = s.execute(
            select(BusinessEvent.id)
            .where(BusinessEvent.target_cls == "core.process")
            .where(BusinessEvent.target_id == int(process_id))
            .where(BusinessEvent.is_deleted.is_(False))
        ).all()
        return len(rows)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-Tests fuer Plan 08 (Events).")
    parser.add_argument("--tenant", default="demo", help="Tenant-Slug (default: demo)")
    args = parser.parse_args()
    slug = args.tenant

    # Reihenfolge wichtig: Plan 08 Offene Frage 5.
    install_change_log_hooks()
    install_event_hooks()

    print(f"[smoke] tenant={slug}", flush=True)
    failures: list[tuple[str, str]] = []

    def _run(name: str, fn, *args_, **kwargs_):
        try:
            return fn(*args_, **kwargs_)
        except Exception as exc:  # noqa: BLE001
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"[FAIL] {name}", flush=True)
            traceback.print_exc()
            return None

    _run("schema_defaults", case_schema_defaults, slug)
    pid = _run("manual_event_actor_from_context", case_manual_event_actor_from_context, slug)
    if pid:
        _run("trace_uid_bridge", case_trace_uid_bridge, slug, pid)

    auto_res = _run("auto_event_from_status_change", case_auto_event_from_status_change, slug)
    if auto_res:
        auto_pid, _ = auto_res
        _run("selective_whitelist", case_selective_whitelist, slug, auto_pid)
        _run("polymorph_filter", case_polymorph_filter, slug, auto_pid)

    _run("semantic_fassade", case_semantic_fassade, slug)

    # event_id fuer soft-delete-Case
    set_tenant(slug)
    set_actor("ai", "smoke_events")
    set_trace_uid("")
    tmp_pid = _create_smoke_process(slug)
    tmp_event = log_event(
        target_cls="core.process",
        target_id=tmp_pid,
        event_type="manual_entry",
        title=f"{SMOKE_PREFIX} for-soft-delete",
    )
    _run("soft_delete_no_change_log", case_soft_delete_no_change_log, slug, tmp_event)

    _run("mcp_tool_smoke", case_mcp_tool_smoke, slug)
    _run("listener_order", case_listener_order, slug)

    print("", flush=True)
    print("=" * 60, flush=True)
    if failures:
        print(f"[done] {len(failures)} Fehler:", flush=True)
        for name, msg in failures:
            print(f"  - {name}: {msg}", flush=True)
        return 1
    print("[done] alle Smoke-Cases ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
