"""Request-scoped Tenant-Kontext.

Wird vom Gateway zu Beginn jedes HTTP-Requests gesetzt und in Tools/Agents
gelesen, um die richtige tenant_<slug>-DB anzuziehen.

Nutzung:
    from lib.tenant_context import set_tenant, get_tenant, require_tenant

    set_tenant("demo")
    slug = require_tenant()         # raises wenn nicht gesetzt
    slug_or_none = get_tenant()

Da wir ContextVars nutzen, ist der Kontext pro asyncio-Task isoliert
(FastAPI hängt jeden Request in einen eigenen Task).
"""
from __future__ import annotations

from contextvars import ContextVar

_tenant_slug: ContextVar[str | None] = ContextVar("wai_tenant_slug", default=None)
_user_id: ContextVar[int | None] = ContextVar("wai_user_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("wai_request_id", default=None)


def set_tenant(slug: str | None) -> None:
    _tenant_slug.set(slug)


def get_tenant() -> str | None:
    return _tenant_slug.get()


def require_tenant() -> str:
    slug = _tenant_slug.get()
    if slug is None:
        raise RuntimeError("Kein Tenant-Kontext gesetzt — set_tenant() vergessen?")
    return slug


def set_user(user_id: int | None) -> None:
    _user_id.set(user_id)


def get_user() -> int | None:
    return _user_id.get()


def set_request_id(rid: str | None) -> None:
    _request_id.set(rid)


def get_request_id() -> str | None:
    return _request_id.get()
