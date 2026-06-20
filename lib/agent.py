"""Helper für Sub-Agent-Spawning mit vollständiger Telemetrie.

Plan 02 (Sub-Agent-Lifecycle-Events). Wird vom Manager-Agent (und künftig
weiteren Agents, die delegieren) genutzt, um einen Sub-Agent unter einem
eigenen Sub-Trace zu starten, dabei ein Sub-AiChat anzulegen, Lifecycle-
Events ``sub_agent_started`` / ``sub_agent_completed`` auf dem Parent-
Emitter zu emittieren (damit SSE-Konsumenten sie live sehen) und den
Sub-Trace in ``logging_db`` mit ``create_trace``/``finalize_trace``
zu klammern.

Aufrufer reicht eine async-Funktion ``fn`` rein, die die folgenden kwargs
akzeptiert: ``sub_emitter``, ``sub_trace_uid``, ``sub_chat_id``,
``tenant_slug`` — plus seine eigentlichen Eingangs-Args. Der Helper
fängt Exceptions und gibt sie als Fehlertext + ``is_error=True`` zurück,
damit der Manager-Tool-Loop sie wie einen normalen Tool-Fehler an den
LLM zurückreicht.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from lib.db import session_for_tenant
from lib.entities.tenant import AiChat
from lib.event_store import create_trace, finalize_trace
from lib.events import EventEmitter, SubEventEmitter, new_trace_uid, now_utc
from lib.logging import get_logger
from lib.tenant_context import get_actor, get_trace_uid, set_actor, set_trace_uid

log = get_logger(__name__)

TASK_BRIEF_PREVIEW_LEN = 200
SUMMARY_PREVIEW_LEN = 300


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
