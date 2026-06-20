"""Smoke-Skript: Plan 07 (Process) Mindest-Cases.

Laeuft als ausfuehrbares Skript gegen einen LAUFENDEN Stack (Postgres
muss erreichbar sein, Tenant ``demo`` muss migriert sein). Deckt die
Plan-07-Mindest-Cases ab, ohne pytest-Setup einzufuehren — das Repo
arbeitet bewusst mit Smoke-Skripten unter ``scripts/`` (vgl.
``scripts/test_all_mcp.py``).

Aufruf:
    docker compose exec -T gateway python scripts/smoke_process.py
    # oder lokal mit gesetzten ENV-Vars (ADMIN_DB_URL etc.):
    python scripts/smoke_process.py [--tenant demo]

Bei Fehler exited der Prozess mit Code 1; auf der Konsole erscheint pro
Case ein ``[ok]``- oder Exception-Output.
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

from sqlalchemy import select  # noqa: E402

from lib.audit import install_change_log_hooks  # noqa: E402
from lib.db import session_for_logging, session_for_tenant  # noqa: E402
from lib.entities.tenant import AiChat, Note, Process, SemanticFassade  # noqa: E402
from lib.polymorphic import validate_target  # noqa: E402
from lib.settings import resolve as settings_resolve  # noqa: E402
from lib.tenant_context import set_tenant  # noqa: E402

SMOKE_PREFIX = "Smoke-Test:"


class SmokeFail(Exception):
    """Markiert ein fehlgeschlagenes Smoke-Case."""


def _ok(case: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"[ok] {case}{suffix}", flush=True)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise SmokeFail(msg)


def _wait_for_fassade(slug: str, process_id: int, *, timeout_s: float = 5.0) -> SemanticFassade | None:
    """Semantic-Sync laeuft outbox-basiert nach after_commit in einer
    eigenen Session — wir pollen kurz, bis die Fassade da ist.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with session_for_tenant(slug) as s:
            row = s.execute(
                select(SemanticFassade)
                .where(SemanticFassade.entity_class == "core.process")
                .where(SemanticFassade.entity_id == int(process_id))
                .where(SemanticFassade.is_deleted.is_(False))
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                return row
        time.sleep(0.2)
    return None


def _latest_entity_change(target_cls: str, target_id: int) -> dict | None:
    """Liest den juengsten EntityChange-Eintrag fuer ein Target."""
    from lib.entities.logging.entity_change import EntityChange  # lazy

    with session_for_logging() as s:
        row = s.execute(
            select(EntityChange)
            .where(EntityChange.target_cls == target_cls)
            .where(EntityChange.target_id == int(target_id))
            .order_by(EntityChange.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "change_type": row.change_type,
            "field_diffs": row.field_diffs or [],
            "summary": row.summary or "",
        }


def case_create_read(slug: str) -> int:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        obj = Process(
            name=f"{SMOKE_PREFIX} Create+Read",
            description="Wird beim Lesen wieder aufgetaucht.",
            kind="smoke",
            status="neu",
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        pid = int(obj.id)
        _assert(obj.id > 0, "Process bekam keine id")
        _assert(obj.status == "neu", f"Default-Status falsch: {obj.status!r}")
        _assert(obj.priority == "normal", f"Default-Priority falsch: {obj.priority!r}")
        _assert(obj.customer_cls == "" and obj.customer_id == 0, "leerer Kunden-Anker erwartet")
        _assert(obj.closed_at is None, "closed_at sollte beim Anlegen None sein")

    with session_for_tenant(slug) as s:
        re = s.get(Process, pid)
        _assert(re is not None and not re.is_deleted, "Process nicht wieder gefunden")
    _ok("create+read+defaults", f"process_id={pid}")
    return pid


def case_change_log_update(slug: str, process_id: int) -> None:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        obj = s.get(Process, process_id)
        _assert(obj is not None, "process nicht gefunden")
        obj.description = "Erweiterte Beschreibung — Change-Log-Trigger."
        s.commit()
    # after_commit ist synchron; der Audit-Drain auch — kurzer Atempunkt nur fuer
    # die zweite Logging-Session.
    time.sleep(0.2)
    entry = _latest_entity_change("core.process", process_id)
    _assert(entry is not None, "kein EntityChange-Eintrag nach Update gefunden")
    _assert(entry["change_type"] == "update", f"change_type={entry['change_type']}")
    fields = [d.get("field") for d in entry["field_diffs"]]
    _assert("description" in fields, f"description nicht im field_diffs: {fields}")
    _ok("change_log update", f"fields={fields}")


def case_status_validator_and_closed_at(slug: str, process_id: int) -> None:
    # update_process aus dem MCP-Modul aufrufen, weil dort die Validierung sitzt.
    set_tenant(slug)
    os.environ.setdefault("WAI_TENANT_SLUG_DEFAULT", slug)
    from mcp_servers.process_mcp.server import set_status, update_process

    bad = update_process(process_id, {"status": "kompletter-quatsch"})
    _assert("error" in bad, f"Validator liess unerlaubten Status durch: {bad}")

    good = set_status(process_id, "abgeschlossen")
    _assert("error" not in good, f"set_status fehlgeschlagen: {good}")
    _assert(good["status"] == "abgeschlossen", f"status={good['status']}")
    _assert(good.get("closed_at"), "closed_at sollte gesetzt sein")

    reopened = set_status(process_id, "in_arbeit")
    _assert(reopened.get("closed_at") in (None, ""), "closed_at sollte zurueckgesetzt sein")
    _ok("status validator + closed_at automatik")


def case_polymorph_note_attach(slug: str, process_id: int) -> int:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        n = Note(
            title=f"{SMOKE_PREFIX} Note an Process",
            body="Polymorpher Anker an core.process.",
            target_cls="core.process",
            target_id=process_id,
        )
        s.add(n)
        s.commit()
        s.refresh(n)
        nid = int(n.id)
        _assert(n.target_cls == "core.process" and n.target_id == process_id, "Note-Anker falsch")
    # validate_target soll den (cls, id)-Paar als ok ansehen
    validate_target("core.process", process_id)
    _ok("polymorpher anker note->process", f"note_id={nid}")
    return nid


def case_nesting_parent(slug: str, parent_id: int) -> None:
    set_tenant(slug)
    os.environ.setdefault("WAI_TENANT_SLUG_DEFAULT", slug)
    from mcp_servers.process_mcp.server import create_process, list_processes

    child = create_process(
        name=f"{SMOKE_PREFIX} Sub-Vorgang",
        description="hat parent_id auf den Smoke-Prozess",
        parent_id=parent_id,
        kind="smoke_child",
    )
    _assert("error" not in child, f"create_process Sub-Vorgang fehlgeschlagen: {child}")
    _assert(child["parent_id"] == parent_id, "parent_id nicht uebernommen")

    kids = list_processes(parent_id=parent_id)
    _assert(any(k["id"] == child["id"] for k in kids), "Sub-Vorgang nicht in list_processes(parent_id=)")
    _ok("nesting parent_id + list_processes filter", f"child_id={child['id']}")


def case_aichat_anker(slug: str, process_id: int) -> None:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        chat = AiChat(
            title=f"{SMOKE_PREFIX} Chat-an-Process",
            user_id=0,
            agent_name="smoke",
            target_cls="core.process",
            target_id=process_id,
        )
        s.add(chat)
        s.commit()
        s.refresh(chat)
        _assert(chat.target_cls == "core.process" and chat.target_id == process_id, "AiChat-Anker falsch")
    _ok("aichat anker -> process", f"chat_id={chat.id}")


def case_semantic_fassade(slug: str, process_id: int) -> None:
    fassade = _wait_for_fassade(slug, process_id)
    _assert(fassade is not None, "SemanticFassade fuer Process nicht angelegt")
    hash_before = fassade.content_hash

    set_tenant(slug)
    with session_for_tenant(slug) as s:
        p = s.get(Process, process_id)
        p.description = (p.description or "") + "\n\nNachtrag fuer Semantic-Rebuild."
        s.commit()

    # Resync laeuft nach commit in einer eigenen Session, daher pollen.
    deadline = time.monotonic() + 5.0
    new_hash = hash_before
    while time.monotonic() < deadline:
        with session_for_tenant(slug) as s:
            row = s.execute(
                select(SemanticFassade)
                .where(SemanticFassade.entity_class == "core.process")
                .where(SemanticFassade.entity_id == int(process_id))
                .where(SemanticFassade.is_deleted.is_(False))
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                new_hash = row.content_hash
                if new_hash != hash_before:
                    break
        time.sleep(0.2)
    _assert(new_hash != hash_before, "content_hash hat sich nach description-Aenderung nicht geaendert")
    _ok("semantic fassade + rebuild on description change")


def case_settings_default(slug: str) -> None:
    val = settings_resolve(
        "process.status.allowed_values",
        tenant=slug,
        entity_cls="core.process",
    )
    _assert(isinstance(val, list) and "in_arbeit" in val, f"unerwartete allowed_values: {val!r}")
    closed = settings_resolve(
        "process.status.closed_values",
        tenant=slug,
        entity_cls="core.process",
    )
    _assert("abgeschlossen" in closed, f"closed_values fehlt 'abgeschlossen': {closed!r}")
    _ok("settings resolver liefert platform default")


def case_mcp_tool_smoke(slug: str) -> None:
    os.environ.setdefault("WAI_TENANT_SLUG_DEFAULT", slug)
    from mcp_servers.process_mcp.server import (
        allowed_status_values,
        archive_process,
        create_process,
        get_process,
        link_to_customer,
        link_to_project,
        list_processes,
        manifest,
        update_process,
    )

    m = manifest()
    _assert(m.get("kind") == "tool", f"manifest.kind={m.get('kind')}")
    _assert("core.process" in (m.get("entities") or []), "entities-Eintrag fehlt")

    created = create_process(
        name=f"{SMOKE_PREFIX} MCP Happy-Path",
        description="MCP-Smoke",
        kind="smoke_mcp",
    )
    _assert("id" in created, f"create_process: {created}")
    pid = int(created["id"])

    got = get_process(pid)
    _assert(got["id"] == pid, "get_process inkonsistent")

    upd = update_process(pid, {"priority": "hoch"})
    _assert(upd.get("priority") == "hoch", f"update_process: {upd}")

    listing = list_processes(kind="smoke_mcp", limit=5)
    _assert(any(r["id"] == pid for r in listing), "list_processes findet smoke_mcp nicht")

    # Projekt 0 = aushaengen — kein Validator, der das blockiert.
    linked = link_to_project(pid, 0)
    _assert(linked.get("project_id") == 0, "link_to_project 0 sollte ok sein")

    # Kunde leer = loesen
    cleared = link_to_customer(pid, "", 0)
    _assert(cleared.get("customer_cls") == "", "link_to_customer mit leeren Werten sollte loesen")

    arch = archive_process(pid)
    _assert(arch.get("ok") is True, f"archive_process: {arch}")
    after = get_process(pid)
    _assert(after.get("error"), "archivierter Process sollte nicht mehr in get_process auftauchen")

    asv = allowed_status_values()
    _assert(isinstance(asv.get("allowed"), list), "allowed_status_values ohne 'allowed'")
    _ok("mcp tools happy path", f"happy_path_process_id={pid}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-Tests fuer Plan 07 (Process).")
    parser.add_argument("--tenant", default="demo", help="Tenant-Slug (default: demo)")
    args = parser.parse_args()
    slug = args.tenant

    install_change_log_hooks()
    # Semantic-Listener werden bereits in lib/entities/tenant/__init__.py registriert.

    print(f"[smoke] tenant={slug}", flush=True)
    failures: list[tuple[str, str]] = []

    def _run(name: str, fn, *args_, **kwargs_):
        try:
            return fn(*args_, **kwargs_)
        except Exception as exc:  # noqa: BLE001 — Smoke faengt alles, listet am Ende
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"[FAIL] {name}", flush=True)
            traceback.print_exc()
            return None

    pid = _run("create_read", case_create_read, slug)
    if pid:
        _run("change_log_update", case_change_log_update, slug, pid)
        _run("status_validator_and_closed_at", case_status_validator_and_closed_at, slug, pid)
        _run("polymorph_note_attach", case_polymorph_note_attach, slug, pid)
        _run("nesting_parent", case_nesting_parent, slug, pid)
        _run("aichat_anker", case_aichat_anker, slug, pid)
        _run("semantic_fassade", case_semantic_fassade, slug, pid)
    _run("settings_default", case_settings_default, slug)
    _run("mcp_tool_smoke", case_mcp_tool_smoke, slug)

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
