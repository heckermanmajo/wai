"""Dev-Seed fuer Demo-Vorgaenge (Plan 07).

Legt idempotent 2-3 Process-Rows im Demo-Tenant an, plus die noetigen
Aufhaenger (1 Demo-Projekt, 1 Demo-Account), damit der Debug-View und
das spaetere Vorgangs-Listing direkt etwas zu zeigen haben.

Idempotenz-Anker: ``Process.name`` ist eindeutig pro Seed-Lauf — ein
Vorgang mit dem gleichen Namen wird nicht doppelt angelegt.

Aufruf:
    python scripts/seed_tenant_demo.py
    python scripts/seed_tenant_demo.py --tenant other_slug
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from lib.db import session_for_tenant  # noqa: E402
from lib.entities.tenant import Account, Process, Project  # noqa: E402
from lib.tenant_context import set_tenant  # noqa: E402

DEMO_PROJECT_NAME = "Demo-Projekt"
DEMO_ACCOUNT_NAME = "Demo Kundenfirma GmbH"


def _ensure_project(s, name: str) -> int:
    row = s.execute(
        select(Project)
        .where(Project.name == name)
        .where(Project.is_deleted.is_(False))
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return int(row.id)
    obj = Project(
        name=name,
        description="Auto-Seed fuer Plan-07-Demo-Vorgaenge.",
        status="active",
    )
    s.add(obj)
    s.flush()
    print(f"[ok] Demo-Projekt angelegt: id={obj.id}")
    return int(obj.id)


def _ensure_account(s, name: str) -> int:
    row = s.execute(
        select(Account)
        .where(Account.name == name)
        .where(Account.is_deleted.is_(False))
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return int(row.id)
    obj = Account(
        name=name,
        industry="Demo",
        email="kontakt@demo-kunde.test",
    )
    s.add(obj)
    s.flush()
    print(f"[ok] Demo-Account angelegt: id={obj.id}")
    return int(obj.id)


def _ensure_process(s, *, name: str, **fields) -> int:
    row = s.execute(
        select(Process)
        .where(Process.name == name)
        .where(Process.is_deleted.is_(False))
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return int(row.id)
    obj = Process(name=name, **fields)
    s.add(obj)
    s.flush()
    print(
        f"[ok] Demo-Vorgang angelegt: id={obj.id} name={name!r} "
        f"status={obj.status} kind={obj.kind!r}"
    )
    return int(obj.id)


def seed(slug: str) -> None:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        project_id = _ensure_project(s, DEMO_PROJECT_NAME)
        account_id = _ensure_account(s, DEMO_ACCOUNT_NAME)

        # 1) An ein Projekt gehaengter Vorgang.
        _ensure_process(
            s,
            name="Reklamation 4711 — defekte Lieferung",
            description=(
                "Kunde meldet beschaedigte Ware aus Lieferung 4711. Foto liegt vor.\n"
                "Naechster Schritt: Ersatzlieferung pruefen, Kulanz-Entscheidung."
            ),
            kind="reklamation",
            status="in_arbeit",
            priority="hoch",
            project_id=project_id,
        )

        # 2) An einen Kunden polymorph gehaengter Vorgang.
        _ensure_process(
            s,
            name="TUEV-Abnahme Maschine M-12",
            description=(
                "Jaehrliche Abnahme der Maschine M-12 beim Kunden. Termin "
                "muss noch koordiniert werden."
            ),
            kind="tuev_abnahme",
            status="wartet_auf_kunde",
            priority="normal",
            customer_cls="crm.account",
            customer_id=account_id,
        )

        # 3) Freistehender Vorgang (kein Projekt, kein Kunde).
        _ensure_process(
            s,
            name="Intern: Lager-Inventur planen",
            description=(
                "Inventur fuer Q3 vorbereiten — Termin, Personal, Zaehlbloecke."
            ),
            kind="intern",
            status="neu",
            priority="niedrig",
        )

        s.commit()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed Demo-Vorgaenge in einem Tenant (idempotent)."
    )
    parser.add_argument("--tenant", default="demo", help="Tenant-Slug (default: demo)")
    args = parser.parse_args()

    if not os.environ.get("TENANT_DB_URL_TEMPLATE"):
        print(
            "[err] TENANT_DB_URL_TEMPLATE nicht gesetzt — siehe docker-compose.yml",
            file=sys.stderr,
        )
        return 2

    seed(args.tenant)
    print(f"[done] Demo-Vorgaenge in Tenant '{args.tenant}' geseedet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
