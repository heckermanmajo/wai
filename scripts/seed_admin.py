"""Dev-Seed: legt Default-User im demo-Tenant an.

Wird von `scripts/start_local.sh` nach `create_tenant.py demo` aufgerufen,
damit eine frische DB sofort Dev-Logins hat. Die Login-Page
(`gateway/ui_login.py`) verspricht allen aufgelisteten Dev-Usern das
Passwort `123` — dieses Script stellt das auch wirklich her.

Idempotent: existierende User bekommen ihr Passwort auf `123` zurueck-
gesetzt; Memberships werden angelegt oder reaktiviert.

Aufruf:
    python scripts/seed_admin.py
    python scripts/seed_admin.py --tenant other_slug
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from lib.seed import ensure_admin_user  # noqa: E402

DEV_PASSWORD = "123"
# Plan 06: demo-User ist Plattform-Admin (Debug-View global), alice Supporter.
DEV_USERS: list[tuple[str, str, str]] = [
    # (username, display_name, platform_role)
    ("demo", "Demo Admin", "admin"),
    ("alice", "Alice", "supporter"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Default-Dev-User in admin_db.")
    parser.add_argument(
        "--tenant",
        default="demo",
        help="Tenant-Slug, in den die User eingehaengt werden (default: demo)",
    )
    args = parser.parse_args()

    if not os.environ.get("ADMIN_DB_URL"):
        print("[err] ADMIN_DB_URL ist nicht gesetzt — siehe docker-compose.yml", file=sys.stderr)
        return 2

    for username, display_name, platform_role in DEV_USERS:
        ensure_admin_user(
            slug=args.tenant,
            username=username,
            password=DEV_PASSWORD,
            display_name=display_name,
            tenant_role="admin",
            platform_role=platform_role,
        )
    print(f"[done] Dev-User in Tenant '{args.tenant}' geseedet (Passwort: {DEV_PASSWORD}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
