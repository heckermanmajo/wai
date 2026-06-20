"""Idempotente Seed-Helper fuer admin_db.

Wird sowohl von `scripts/create_tenant.py` (Single-User-Variante mit
--admin-username) als auch von `scripts/seed_admin.py` (Dev-Stack-Seed)
benutzt, damit die Logik nicht doppelt rumliegt.
"""
from __future__ import annotations

from sqlalchemy import select

from lib.auth import hash_password
from lib.db import session_for_admin
from lib.entities.admin import Tenant, TenantMembership, UserData


def ensure_admin_user(
    slug: str,
    username: str,
    password: str,
    display_name: str = "",
    tenant_role: str = "admin",
    platform_role: str = "none",
) -> None:
    """Legt UserData + TenantMembership an / synchronisiert Passwort.

    - Tenant muss in admin_db existieren (sonst Warning + No-Op).
    - User wird neu angelegt oder Passwort wird ueberschrieben (idempotent
      heisst hier: gleiches Endpasswort, nicht "nichts tun bei Existenz").
    - Membership wird angelegt oder auf is_active=True gesetzt.
    - ``platform_role`` (Plan 06) wird auf neuen User uebernommen ODER auf
      bestehenden hochgesetzt, wenn der Default "none" ist. Bewusste
      Downgrades macht der Seed nicht — admin bleibt admin.
    """
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
                platform_role=platform_role,
                is_active=True,
                display_name=display_name or username,
            )
            s.add(user)
            s.flush()
            print(f"[ok] UserData '{username}' angelegt (id={user.id}, platform_role={platform_role})")
        else:
            user.password_hash = hash_password(password)
            # Upgrade: none -> {supporter, admin}. Downgrade niemals.
            if (user.platform_role or "none") == "none" and platform_role != "none":
                user.platform_role = platform_role
                print(
                    f"[info] UserData '{username}' platform_role auf {platform_role} hochgesetzt"
                )
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
                    tenant_role=tenant_role,
                    is_active=True,
                )
            )
            print(
                f"[ok] TenantMembership angelegt "
                f"(user='{username}', tenant='{slug}', role={tenant_role})"
            )
        else:
            membership.is_active = True
            print(f"[info] TenantMembership existiert (user='{username}', tenant='{slug}')")

        s.commit()
