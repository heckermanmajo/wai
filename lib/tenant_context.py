"""Request-scoped Tenant-Kontext.

Wird vom Gateway zu Beginn jedes HTTP-Requests gesetzt und in Tools/Agents
gelesen, um die richtige tenant_<slug>-DB anzuziehen.

Nutzung:
    from lib.tenant_context import set_tenant, get_tenant, require_tenant

    set_tenant("demo")
    slug = require_tenant()         # raises wenn nicht gesetzt
    slug_or_none = get_tenant()

Trace- und Actor-Kontext werden analog gesetzt und von nachgelagerten
Schichten (Events, Change-Log, Sub-Agents) gelesen, statt sie durch alle
Aufrufpfade durchzureichen:

    from lib.tenant_context import set_trace_uid, set_actor, get_actor

    set_trace_uid("trace_abc123")
    set_actor("ai", "sales_support")     # actor_type in {"human", "ai"}
    actor_type, agent_name = get_actor()

Da wir ContextVars nutzen, ist der Kontext pro asyncio-Task isoliert
(FastAPI hängt jeden Request in einen eigenen Task).
"""
from __future__ import annotations

from contextvars import ContextVar

_tenant_slug: ContextVar[str | None] = ContextVar("wai_tenant_slug", default=None)
_user_id: ContextVar[int | None] = ContextVar("wai_user_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("wai_request_id", default=None)
_trace_uid: ContextVar[str | None] = ContextVar("wai_trace_uid", default=None)
_actor_type: ContextVar[str] = ContextVar("wai_actor_type", default="human")
_agent_name: ContextVar[str] = ContextVar("wai_agent_name", default="")


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


def set_trace_uid(uid: str | None) -> None:
    _trace_uid.set(uid)


def get_trace_uid() -> str | None:
    return _trace_uid.get()


def set_actor(actor_type: str, agent_name: str = "") -> None:
    if actor_type not in {"human", "ai"}:
        raise ValueError(f"Ungültiger actor_type: {actor_type}. Erlaubt: human, ai")
    _actor_type.set(actor_type)
    _agent_name.set(agent_name)


def get_actor() -> tuple[str, str]:
    return _actor_type.get(), _agent_name.get()
