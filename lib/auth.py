"""Auth-Layer fuers Gateway.

Username+Passwort gegen UserData.password_hash (bcrypt ueber passlib).
Session-Cookie ist ein itsdangerous-signiertes JSON-Dict
{user_id, tenant_slug}. Tenant kommt aus dem URL-Path (z.B. /demo/...),
nicht aus dem Cookie — der Cookie haelt nur die Zugehoerigkeit, damit
wir Cross-Tenant-Spoofing erkennen.

Nutzung im Gateway:

    from fastapi import Depends, Request
    from lib.auth import require_user, UserContext

    @app.get("/{slug}/chats")
    async def list_chats(slug: str, ctx: UserContext = Depends(require_user)):
        ...

require_user liest slug aus dem Path-Parameter `slug`, prueft Cookie
und TenantMembership, ruft set_tenant(slug) + set_user(user_id),
liefert UserContext. Bei Fehler 401 (oder Redirect, siehe
require_user_redirect-Variante fuer HTML-Routen).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext
from sqlalchemy import or_, select

from lib.db import session_for_admin
from lib.entities.admin.membership import TenantMembership
from lib.entities.admin.tenant import Tenant
from lib.entities.admin.user import UserData
from lib.tenant_context import set_tenant, set_user

SESSION_COOKIE_NAME = "wai_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 Tage

_pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _serializer() -> URLSafeSerializer:
    secret = os.environ.get("WAI_SECRET_KEY")
    if not secret:
        raise RuntimeError("WAI_SECRET_KEY nicht gesetzt")
    return URLSafeSerializer(secret, salt="wai-session")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return _pwd_ctx.verify(plain, hashed)
    except ValueError:
        return False


def create_session_token(user_id: int, tenant_slug: str) -> str:
    return _serializer().dumps({"user_id": user_id, "tenant_slug": tenant_slug})


def read_session_token(token: str) -> dict | None:
    try:
        data = _serializer().loads(token)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("user_id"), int):
        return None
    if not isinstance(data.get("tenant_slug"), str):
        return None
    return data


def _pending_serializer() -> URLSafeSerializer:
    secret = os.environ.get("WAI_SECRET_KEY")
    if not secret:
        raise RuntimeError("WAI_SECRET_KEY nicht gesetzt")
    return URLSafeSerializer(secret, salt="wai-pending-pick")


def create_pending_pick_token(user_id: int) -> str:
    """Signiert nur die user_id — fuer den Tenant-Picker zwischen /login und /login/pick."""
    return _pending_serializer().dumps({"user_id": user_id})


def read_pending_pick_token(token: str) -> int | None:
    try:
        data = _pending_serializer().loads(token)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    uid = data.get("user_id")
    return uid if isinstance(uid, int) else None


@dataclass(frozen=True)
class UserContext:
    user_id: int
    username: str
    display_name: str
    tenant_slug: str
    tenant_id: int
    tenant_role: str
    platform_role: str = "none"  # Plan 06 — "admin" | "supporter" | "none"


def is_debug_user_role(platform_role: str) -> bool:
    """Plan 06 — admin und supporter duerfen den Debug-View nutzen."""
    return platform_role in ("admin", "supporter")


def _load_user_context(user_id: int, tenant_slug: str) -> UserContext | None:
    with session_for_admin() as s:
        tenant = s.scalar(
            select(Tenant).where(
                Tenant.slug == tenant_slug,
                Tenant.is_active.is_(True),
                Tenant.is_deleted.is_(False),
            )
        )
        if tenant is None:
            return None
        user = s.scalar(
            select(UserData).where(
                UserData.id == user_id,
                UserData.is_active.is_(True),
                UserData.is_deleted.is_(False),
            )
        )
        if user is None:
            return None
        membership = s.scalar(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.is_active.is_(True),
                TenantMembership.is_deleted.is_(False),
            )
        )
        if membership is None:
            return None
        return UserContext(
            user_id=user.id,
            username=user.username,
            display_name=user.display_name or user.username,
            tenant_slug=tenant.slug,
            tenant_id=tenant.id,
            tenant_role=membership.tenant_role,
            platform_role=user.platform_role or "none",
        )


def authenticate(tenant_slug: str, username: str, password: str) -> UserContext | None:
    with session_for_admin() as s:
        user = s.scalar(
            select(UserData).where(
                UserData.username == username,
                UserData.is_active.is_(True),
                UserData.is_deleted.is_(False),
            )
        )
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        user_id = user.id
    return _load_user_context(user_id, tenant_slug)


@dataclass(frozen=True)
class GlobalAuthResult:
    """Ergebnis von authenticate_global — User identifiziert, Tenant noch offen."""
    user_id: int
    username: str
    display_name: str
    tenants: list[tuple[str, str]]  # (slug, display_name) der aktiven Memberships


def authenticate_global(login: str, password: str) -> GlobalAuthResult | None:
    """Sucht User per username ODER email, prueft Passwort, listet aktive Tenants.

    Liefert None bei unbekanntem User/falschem Passwort. Tenant-Auswahl
    erfolgt im Caller (Auto-Login bei 1 Tenant, Picker bei >1).
    """
    login = (login or "").strip()
    if not login:
        return None
    with session_for_admin() as s:
        user = s.scalar(
            select(UserData).where(
                or_(UserData.username == login, UserData.email == login),
                UserData.is_active.is_(True),
                UserData.is_deleted.is_(False),
            )
        )
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        rows = s.execute(
            select(Tenant.slug, Tenant.name)
            .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
            .where(
                TenantMembership.user_id == user.id,
                TenantMembership.is_active.is_(True),
                TenantMembership.is_deleted.is_(False),
                Tenant.is_active.is_(True),
                Tenant.is_deleted.is_(False),
            )
            .order_by(Tenant.slug.asc())
        ).all()
        return GlobalAuthResult(
            user_id=user.id,
            username=user.username,
            display_name=user.display_name or user.username,
            tenants=[(slug, name or slug) for slug, name in rows],
        )


def list_dev_users() -> list[dict]:
    """Alle aktiven User + ihre Tenants — fuer die Dev-Login-Page.

    NUR fuer Entwicklung gedacht. Liefert username, email, display_name
    sowie eine Liste der Tenant-Slugs pro User.
    """
    with session_for_admin() as s:
        users = s.execute(
            select(UserData)
            .where(UserData.is_active.is_(True), UserData.is_deleted.is_(False))
            .order_by(UserData.username.asc())
        ).scalars().all()
        out: list[dict] = []
        for u in users:
            slugs = s.execute(
                select(Tenant.slug)
                .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
                .where(
                    TenantMembership.user_id == u.id,
                    TenantMembership.is_active.is_(True),
                    TenantMembership.is_deleted.is_(False),
                    Tenant.is_active.is_(True),
                    Tenant.is_deleted.is_(False),
                )
                .order_by(Tenant.slug.asc())
            ).scalars().all()
            out.append(
                {
                    "username": u.username,
                    "email": u.email or "",
                    "display_name": u.display_name or u.username,
                    "tenants": list(slugs),
                }
            )
        return out


def _ctx_from_request(request: Request, slug: str) -> UserContext | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    data = read_session_token(token)
    if data is None:
        return None
    if data["tenant_slug"] != slug:
        return None
    return _load_user_context(data["user_id"], slug)


def _ctx_from_cookie_only(request: Request) -> UserContext | None:
    """Liest Session-Cookie ohne Slug-Bindung aus URL — Tenant kommt aus dem Cookie.

    Genutzt vom /me-Endpoint, den der Next.js-Client vor jedem Tenant-Routing aufruft.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    data = read_session_token(token)
    if data is None:
        return None
    return _load_user_context(data["user_id"], data["tenant_slug"])


def require_user(slug: str, request: Request) -> UserContext:
    """FastAPI-Dependency fuer JSON-Endpoints — wirft 401 bei Fehler."""
    ctx = _ctx_from_request(request, slug)
    if ctx is None:
        raise HTTPException(status_code=401, detail="nicht eingeloggt")
    set_tenant(ctx.tenant_slug)
    set_user(ctx.user_id)
    return ctx


@dataclass(frozen=True)
class DebugUser:
    """Plan 06 — Debug-View User-Kontext (kein Tenant aus URL-Path).

    Memberships listet die Tenant-Slugs, auf die der User Zugriff hat.
    Plattform-Admin sieht alle Tenants (memberships kann hier leer sein —
    Caller prueft platform_role und reduziert ggf. nicht).
    """
    user_id: int
    username: str
    display_name: str
    platform_role: str
    memberships: list[str]


def _load_debug_user(user_id: int) -> DebugUser | None:
    with session_for_admin() as s:
        user = s.scalar(
            select(UserData).where(
                UserData.id == user_id,
                UserData.is_active.is_(True),
                UserData.is_deleted.is_(False),
            )
        )
        if user is None:
            return None
        if not is_debug_user_role(user.platform_role or "none"):
            return None
        rows = s.execute(
            select(Tenant.slug)
            .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
            .where(
                TenantMembership.user_id == user.id,
                TenantMembership.is_active.is_(True),
                TenantMembership.is_deleted.is_(False),
                Tenant.is_active.is_(True),
                Tenant.is_deleted.is_(False),
            )
        ).scalars().all()
    return DebugUser(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        platform_role=user.platform_role or "none",
        memberships=list(rows),
    )


def require_debug_user(request: Request) -> DebugUser:
    """FastAPI-Dependency fuer Debug-View-Endpoints. 401 bei Logout, 403 bei fehlender Rolle."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="nicht eingeloggt")
    data = read_session_token(token)
    if data is None:
        raise HTTPException(status_code=401, detail="nicht eingeloggt")
    debug = _load_debug_user(data["user_id"])
    if debug is None:
        raise HTTPException(status_code=403, detail="kein Debug-View-Zugriff")
    set_user(debug.user_id)
    return debug


def require_user_redirect(slug: str, request: Request) -> UserContext | RedirectResponse:
    """Variante fuer HTML-Routen — gibt RedirectResponse zurueck statt 401.

    Caller muessen den Returntyp pruefen und Response direkt zurueckgeben.
    """
    ctx = _ctx_from_request(request, slug)
    if ctx is None:
        return RedirectResponse(url="/login", status_code=303)
    set_tenant(ctx.tenant_slug)
    set_user(ctx.user_id)
    return ctx
