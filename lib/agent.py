"""Helper für Sub-Agent-Spawning mit vollständiger Telemetrie.

Plan 02 (Sub-Agent-Lifecycle-Events). Wird vom Manager-Agent (und künftig
weiteren Agents, die delegieren) genutzt, um einen Sub-Agent unter einem
eigenen Sub-Trace zu starten, dabei ein Sub-AiChat anzulegen, Lifecycle-
Events ``sub_agent_started`` / ``sub_agent_completed`` auf dem Parent-
Emitter zu emittieren (damit SSE-Konsumenten sie live sehen) und den
Sub-Trace in ``logging_db`` mit ``create_trace``/``finalize_trace``
zu klammern.

Plan 05 — MCP-Kind: zusaetzlich Discovery-/Routing-Helper. Jeder MCP
exponiert ein ``manifest``-Tool mit ``kind in {tool, sub_agent, mixed}``.
``lookup_tool_kind(name)`` liefert den Kind aus dem zentralen Cache, sodass
der Manager nicht mehr hartkodiert ``if name == "sales_support"`` braucht.

Aufrufer reicht eine async-Funktion ``fn`` rein, die die folgenden kwargs
akzeptiert: ``sub_emitter``, ``sub_trace_uid``, ``sub_chat_id``,
``tenant_slug`` — plus seine eigentlichen Eingangs-Args. Der Helper
fängt Exceptions und gibt sie als Fehlertext + ``is_error=True`` zurück,
damit der Manager-Tool-Loop sie wie einen normalen Tool-Fehler an den
LLM zurückreicht.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Awaitable, Callable

from mcp import ClientSession
from mcp.client.sse import sse_client

from lib.db import session_for_tenant
from lib.entities.tenant import AiChat
from lib.event_store import create_trace, finalize_trace
from lib.events import EventEmitter, SubEventEmitter, new_trace_uid, now_utc
from lib.logging import get_logger
from lib.tenant_context import get_actor, get_trace_uid, set_actor, set_trace_uid

log = get_logger(__name__)

TASK_BRIEF_PREVIEW_LEN = 200
SUMMARY_PREVIEW_LEN = 300

# ---------------------------------------------------------------------------
# MCP-Endpoint-Registry + Discovery (Plan 05)
# ---------------------------------------------------------------------------

# Statische Registry — Discovery zur Laufzeit kommt erst in Welle 6.
# Schluessel = logischer Name (frei waehlbar), Wert = SSE-URL.
MCP_ENDPOINTS: list[tuple[str, str]] = [
    ("crm", os.environ.get("MCP_CRM_URL", "http://crm_mcp:8001/sse")),
    ("debug", os.environ.get("MCP_DEBUG_URL", "http://debug_mcp:8001/sse")),
    ("mock", os.environ.get("MCP_MOCK_URL", "http://mcp_mock:8001/sse")),
    ("sales_support",
     os.environ.get("MCP_SALES_SUPPORT_URL", "http://sales_support:8001/sse")),
]

_MANIFEST_CACHE: dict[str, tuple[float, dict]] = {}
_MANIFEST_TTL_SECONDS = 60.0


async def fetch_manifest(url: str) -> dict:
    """Holt den ``manifest()``-Tool-Output eines MCP-Servers.

    Liefert ``{"status": "offline", "error": "..."}`` bei Verbindungsfehlern
    — wichtig fuer den Debug-View, damit ein offline-MCP die Liste nicht
    sprengt. Cache 60s.
    """
    now = time.monotonic()
    cached = _MANIFEST_CACHE.get(url)
    if cached is not None and cached[0] > now:
        return cached[1]
    try:
        async with sse_client(url=url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool("manifest", {})
                raw = " ".join(
                    c.text for c in result.content if hasattr(c, "text")
                )
                try:
                    parsed = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    parsed = {"raw": raw}
        if not isinstance(parsed, dict):
            parsed = {"raw": parsed}
        parsed.setdefault("status", "online")
        _MANIFEST_CACHE[url] = (now + _MANIFEST_TTL_SECONDS, parsed)
        return parsed
    except Exception as exc:  # noqa: BLE001 — Discovery muss robust bleiben
        log.warning("mcp_manifest_fetch_failed url=%s error=%s", url, exc)
        offline = {
            "status": "offline",
            "url": url,
            "error": str(exc),
            "kind": "unknown",
            "tools": [],
        }
        _MANIFEST_CACHE[url] = (now + _MANIFEST_TTL_SECONDS, offline)
        return offline


async def list_all_capabilities() -> dict[str, dict]:
    """Discoveryt alle MCP_ENDPOINTS parallel und liefert {name: manifest}."""
    tasks = [fetch_manifest(url) for _name, url in MCP_ENDPOINTS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, dict] = {}
    for (name, url), res in zip(MCP_ENDPOINTS, results):
        if isinstance(res, Exception):
            out[name] = {"status": "offline", "url": url, "error": str(res),
                         "kind": "unknown", "tools": []}
        else:
            out[name] = res
    return out


async def lookup_tool_kind(tool_name: str) -> str:
    """Liefert 'function' | 'sub_agent' | 'mixed' fuer einen Tool-Namen.

    Sucht in den gemergten Manifesten — pro Tool ist ``kind`` explizit
    angegeben, fallback ist der MCP-Default-Kind.
    """
    caps = await list_all_capabilities()
    for _name, manifest in caps.items():
        if manifest.get("status") == "offline":
            continue
        default_kind = manifest.get("kind", "tool")
        for t in manifest.get("tools", []):
            if t.get("name") == tool_name:
                tk = t.get("kind") or default_kind
                # Plan 05 vereinheitlicht: tool == function.
                return "function" if tk == "tool" else tk
    return "function"


async def find_endpoint_for_tool(tool_name: str) -> str | None:
    """Liefert die SSE-URL eines MCP, der ``tool_name`` exposed."""
    caps = await list_all_capabilities()
    for name, manifest in caps.items():
        if manifest.get("status") == "offline":
            continue
        for t in manifest.get("tools", []):
            if t.get("name") == tool_name:
                for n, url in MCP_ENDPOINTS:
                    if n == name:
                        return url
    return None


def reset_manifest_cache() -> None:
    """Nur fuer Tests / manuelle Resets."""
    _MANIFEST_CACHE.clear()


def _read_parent_anchor(tenant_slug: str, parent_chat_id: int) -> tuple[str, int]:
    """Liest den polymorphen Anker des Parent-Chats (Plan 01). Leer wenn unverankert."""
    with session_for_tenant(tenant_slug) as s:
        chat = s.get(AiChat, parent_chat_id)
        if chat is None:
            return ("", 0)
        return (chat.target_cls or "", chat.target_id or 0)


def _create_sub_chat(
    tenant_slug: str,
    parent_chat_id: int,
    parent_tool_call_id: int,
    role: str,
    user_id: int,
    target_cls: str,
    target_id: int,
) -> int:
    """Legt einen Sub-AiChat an und gibt seine ID zurück."""
    with session_for_tenant(tenant_slug) as s:
        parent = s.get(AiChat, parent_chat_id)
        depth = (parent.depth + 1) if parent is not None else 1
        sub = AiChat(
            title=f"Sub-Chat ({role})",
            user_id=user_id,
            agent_name=role,
            parent_chat_id=parent_chat_id,
            parent_tool_call_id=parent_tool_call_id,
            depth=depth,
            target_cls=target_cls,
            target_id=target_id,
        )
        s.add(sub)
        s.commit()
        return sub.id


async def emit_sub_agent_call(
    *,
    parent_emitter: EventEmitter,
    role: str,
    parent_chat_id: int,
    parent_tool_call_id: int,
    tenant_slug: str,
    user_id: int,
    task: str,
    fn: Callable[..., Awaitable[str]],
    **fn_kwargs,
) -> tuple[str, bool]:
    """Spawnt einen Sub-Agent mit kompletter Telemetrie + Sub-Persistenz.

    Returns (result_text, is_error). Exceptions des Sub-Agents werden hier
    gefangen und als Fehlertext zurückgegeben, damit der aufrufende Tool-
    Loop sie wie einen normalen Tool-Fehler weiterreichen kann.
    """
    parent_trace_uid = parent_emitter.trace_uid
    sub_trace_uid = new_trace_uid()
    started_at = now_utc()
    t0 = time.monotonic()

    target_cls, target_id = _read_parent_anchor(tenant_slug, parent_chat_id)
    sub_chat_id = await asyncio.to_thread(
        _create_sub_chat,
        tenant_slug,
        parent_chat_id,
        parent_tool_call_id,
        role,
        user_id,
        target_cls,
        target_id,
    )
    await asyncio.to_thread(create_trace, sub_trace_uid, tenant_slug, task, started_at)

    sub_emitter = SubEventEmitter(
        sub_trace_uid=sub_trace_uid,
        tenant_id=tenant_slug,
        user_message=task,
        parent_emitter=parent_emitter,
    )

    task_brief = task.strip()
    if len(task_brief) > TASK_BRIEF_PREVIEW_LEN:
        task_brief = task_brief[:TASK_BRIEF_PREVIEW_LEN] + "…"
    parent_emitter.emit(
        "sub_agent_started",
        role=role,
        parent_trace_uid=parent_trace_uid,
        sub_trace_uid=sub_trace_uid,
        sub_chat_id=sub_chat_id,
        task_brief=task_brief,
    )

    prev_actor = get_actor()
    prev_trace = get_trace_uid()
    set_actor("ai", role)
    set_trace_uid(sub_trace_uid)

    status = "ok"
    is_error = False
    result_text: str = ""
    try:
        result_text = await fn(
            task,
            sub_emitter=sub_emitter,
            sub_trace_uid=sub_trace_uid,
            sub_chat_id=sub_chat_id,
            tenant_slug=tenant_slug,
            user_id=user_id,
            **fn_kwargs,
        ) or ""
    except Exception as exc:  # noqa: BLE001 — wir wollen jede Exception in den Tool-Channel überführen
        status = "error"
        is_error = True
        result_text = f"Sub-Agent-Fehler ({role}): {exc!r}"
        log.exception("sub_agent_failed role=%s sub_trace_uid=%s", role, sub_trace_uid)
        sub_emitter.emit("error", error_type=type(exc).__name__, message=str(exc))
    finally:
        set_actor(*prev_actor)
        set_trace_uid(prev_trace)

    duration_ms = int((time.monotonic() - t0) * 1000)
    summary = result_text.strip()
    if len(summary) > SUMMARY_PREVIEW_LEN:
        summary = summary[:SUMMARY_PREVIEW_LEN] + "…"
    parent_emitter.emit(
        "sub_agent_completed",
        role=role,
        sub_trace_uid=sub_trace_uid,
        summary=summary,
        duration_ms=duration_ms,
        status=status,
        outcome_preview="",
    )

    finished_at = now_utc()
    await asyncio.to_thread(
        finalize_trace,
        sub_trace_uid,
        response=result_text,
        intent="",
        status=status,
        finished_at=finished_at,
        duration_ms=duration_ms,
        event_count=sub_emitter.event_count,
        tool_call_count=0,
        error_message="" if status == "ok" else result_text[:300],
    )

    return result_text, is_error


async def _call_sub_agent_via_mcp(
    task: str,
    *,
    sub_emitter: EventEmitter,
    sub_trace_uid: str,
    sub_chat_id: int,
    tenant_slug: str,
    user_id: int,
    mcp_url: str,
    tool_name: str,
) -> str:
    """Macht einen MCP-Tool-Call zu einem Sub-Agent-Server.

    Wird als ``fn`` in ``emit_sub_agent_call`` verwendet, sodass der Manager
    keinen Sonderpfad mehr braucht — der MCP-Call laeuft genauso
    geklammert wie ein lokaler Funktions-Call.
    """
    sub_emitter.emit("mcp_connected", url=mcp_url, tool_names=[tool_name])
    args = {
        "task": task,
        "tenant_slug": tenant_slug,
        "sub_trace_uid": sub_trace_uid,
        "sub_chat_id": int(sub_chat_id),
        "user_id": int(user_id),
    }
    try:
        async with sse_client(url=mcp_url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                text = " ".join(c.text for c in result.content if hasattr(c, "text"))
        return text
    except (ConnectionRefusedError, OSError) as exc:
        sub_emitter.emit("error", error_type="mcp_unreachable", message=str(exc))
        return (
            f"Sub-Agent {tool_name!r} nicht erreichbar ({mcp_url}): {exc!r}"
        )


async def invoke_sub_agent_via_mcp(
    *,
    parent_emitter: EventEmitter,
    role: str,
    parent_chat_id: int,
    parent_tool_call_id: int,
    tenant_slug: str,
    user_id: int,
    task: str,
    mcp_url: str,
    tool_name: str | None = None,
) -> tuple[str, bool]:
    """Sub-Agent-Lifecycle + MCP-Tool-Call statt lokalem Funktions-Call.

    Plan 05 — der Manager nutzt das ueber den ``kind="sub_agent"``-Branch,
    statt eines hartkodierten ``if name == "sales_support"``.
    """
    return await emit_sub_agent_call(
        parent_emitter=parent_emitter,
        role=role,
        parent_chat_id=parent_chat_id,
        parent_tool_call_id=parent_tool_call_id,
        tenant_slug=tenant_slug,
        user_id=user_id,
        task=task,
        fn=_call_sub_agent_via_mcp,
        mcp_url=mcp_url,
        tool_name=tool_name or role,
    )
