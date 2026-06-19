"""Legt einen neuen Tenant an: physische DB + pgvector + Alembic-Migration.

Aufruf:
    python scripts/create_tenant.py <slug> [--admin-username U --admin-password P]
    python scripts/create_tenant.py demo
    python scripts/create_tenant.py gaertnerei_mueller --admin-username inhaber

Der Slug wird streng validiert ([a-z0-9_]+). Verwende `lib.slugify.slugify_tenant`
auf User-Input (z.B. "Gärtnerei Müller GmbH" -> "gaertnerei_mueller_gmbh").

Wenn --admin-username gesetzt ist, wird zusaetzlich ein UserData angelegt
(falls noch nicht vorhanden) und eine TenantMembership mit tenant_role="admin"
in der admin_db verknuepft. Passwort kommt entweder aus --admin-password oder
wird interaktiv via getpass abgefragt.
"""
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

from lib.db import server_url_without_db, tenant_db_url  # noqa: E402
from lib.slugify import is_valid_slug, slugify_tenant  # noqa: E402


def _db_exists(conn, db_name: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name}
    ).first()
    return row is not None


def _create_database(slug: str) -> str:
    db_name = f"tenant_{slug}"
    server_url = server_url_without_db()
    eng = create_engine(server_url, isolation_level="AUTOCOMMIT", future=True)
    with eng.connect() as conn:
        if _db_exists(conn, db_name):
            print(f"[info] DB {db_name} existiert bereits — überspringe CREATE")
        else:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            print(f"[ok] CREATE DATABASE {db_name}")
    eng.dispose()

    tenant_eng = create_engine(tenant_db_url(slug), future=True)
    with tenant_eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print(f"[ok] pgvector aktiviert in {db_name}")
    tenant_eng.dispose()
    return db_name


def _run_tenant_migrations(slug: str) -> None:
    cmd = [
        "alembic",
        "-c",
        str(_PROJECT_ROOT / "alembic-tenant.ini"),
        "-x",
        f"tenant_slug={slug}",
        "upgrade",
        "head",
    ]
    print(f"[run] {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=_PROJECT_ROOT)


def _ensure_admin_tenant_row(slug: str) -> None:
    """Legt eine Row in admin_db.tenant an, falls noch nicht vorhanden.

    Wird best-effort ausgefuehrt: wenn die Entities oder die Tabelle noch
    nicht existieren, ueberspringen wir den Schritt — die DB+Migration
    wurde bereits angelegt, das ist der eigentliche Zweck des Scripts.
    """
    try:
        from lib.db import session_for_admin
        from lib.entities.admin import Tenant
    except ImportError as exc:
        print(f"[info] admin-Entities noch nicht verfuegbar ({exc}) — ueberspringe Tenant-Row")
        return

    try:
        with session_for_admin() as s:
            row = s.execute(
                text("SELECT 1 FROM tenant WHERE slug = :slug"), {"slug": slug}
            ).first()
            if row is not None:
                print(f"[info] Tenant-Row fuer '{slug}' existiert bereits in admin_db")
                return
            s.add(Tenant(name=slug, slug=slug, is_active=True))
            s.commit()
            print(f"[ok] Tenant-Row in admin_db angelegt (slug='{slug}')")
    except Exception as exc:  # noqa: BLE001 — wir wollen das Script nicht abbrechen
        print(f"[warn] Konnte Tenant-Row in admin_db nicht anlegen: {exc}")


def _ensure_admin_user(
    slug: str,
    username: str,
    password: str,
    display_name: str = "",
) -> None:
    """Legt UserData + TenantMembership in admin_db an (idempotent)."""
    from sqlalchemy import select

    from lib.auth import hash_password
    from lib.db import session_for_admin
    from lib.entities.admin import Tenant, TenantMembership, UserData

    with session_for_admin() as s:
        tenant = s.scalar(select(Tenant).where(Tenant.slug == slug))
        if tenant is None:
            print(f"[warn] kein Tenant '{slug}' in admin_db — User kann nicht verknuepft werden")
            return

        user = s.scalar(select(UserData).where(UserData.username == username))
        if user is None:
            user = UserData(
                username=username,
                password_hash=hash_password(password),
                platform_role="none",
                is_active=True,
                display_name=display_name or username,
            )
            s.add(user)
            s.flush()
            print(f"[ok] UserData '{username}' angelegt (id={user.id})")
        else:
            user.password_hash = hash_password(password)
            print(f"[info] UserData '{username}' existiert — Passwort wurde aktualisiert")

        membership = s.scalar(
            select(TenantMembership).where(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == tenant.id,
            )
        )
        if membership is None:
            s.add(
                TenantMembership(
                    user_id=user.id,
                    tenant_id=tenant.id,
                    tenant_role="admin",
                    is_active=True,
                )
            )
            print(f"[ok] TenantMembership angelegt (user='{username}', tenant='{slug}', role=admin)")
        else:
            membership.is_active = True
            print(f"[info] TenantMembership existiert (user='{username}', tenant='{slug}')")

        s.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Lege einen neuen Tenant an.")
    parser.add_argument("slug", help="ASCII-Slug ([a-z0-9_]+) oder freier Name (wird transliteriert)")
    parser.add_argument("--skip-migration", action="store_true", help="Nur DB+pgvector, keine Alembic-Migration")
    parser.add_argument("--admin-username", help="Username des Admin-Users (legt User + Membership an)")
    parser.add_argument("--admin-password", help="Passwort (sonst interaktiv via getpass)")
    parser.add_argument("--admin-display-name", default="", help="Anzeigename des Admin-Users")
    args = parser.parse_args()

    slug = args.slug
    if not is_valid_slug(slug):
        normalized = slugify_tenant(slug)
        print(f"[info] '{slug}' ist kein gültiger Slug — verwende '{normalized}'")
        slug = normalized

    for env in ("ADMIN_DB_URL", "TENANT_DB_URL_TEMPLATE"):
        if not os.environ.get(env):
            print(f"[err] {env} ist nicht gesetzt — siehe docker-compose.yml", file=sys.stderr)
            return 2

    _create_database(slug)
    if not args.skip_migration:
        _run_tenant_migrations(slug)
    _ensure_admin_tenant_row(slug)

    if args.admin_username:
        password = args.admin_password
        if not password:
            password = getpass.getpass(f"Passwort fuer '{args.admin_username}': ")
            if not password:
                print("[err] leeres Passwort", file=sys.stderr)
                return 2
        _ensure_admin_user(slug, args.admin_username, password, args.admin_display_name)

    print(f"[done] Tenant '{slug}' bereit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
