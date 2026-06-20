"""Manager-Agent — async orchestrator with dynamic MCP tool loading.

Two-tier LLM: Tier1 für Intent-Klassifizierung, Tier2 für Reasoning + Tool-Calls.
MCP-Anbindung via SSE ClientSession. sales_support läuft als Sub-Agent.

Persistenz: chat() bekommt eine chat_id (existierender AiChat) und
schreibt User/Assistant/Tool-Messages + AiToolCall-Zeilen in die
Tenant-DB. Aus dem AiChat wird beim Start die History geladen — der
Browser uebergibt keine History mehr. Tool-Calls, die bekannte CRM-
Entities adressieren, werden zusaetzlich als ChatArtifact gepinnt
(Mappen-Tracking, siehe lib/entities/tenant/chat_artifact.py).

Telemetrie: chat() akzeptiert optional einen EventEmitter. Wenn übergeben,
werden alle relevanten Übergänge (Intent, MCP-Connect, LLM-Calls, Tool-Calls,
Errors) strukturiert emittiert — der SSE-Handler im Gateway streamt sie live
an den Client und persistiert sie in logging_db.
"""
import asyncio
import json
import os
import time

from mcp import ClientSession
from mcp.client.sse import sse_client

from agents.manager.provider import get_client, get_tier1_model, get_tier2_model
from agents.sales_support.agent import run_sales_support
from lib.agent import emit_sub_agent_call
from lib.chat_persist import load_history, persist_exchange
from lib.db import session_for_tenant
from lib.entities.tenant import AiChat
from lib.events import EventEmitter
from lib.logging import get_logger
from lib.tenant_context import get_tenant, get_user, set_actor

log = get_logger(__name__)

MCP_LEAD_URL = os.environ.get("MCP_LEAD_URL", "http://localhost:8001/sse")
SYSTEM_PROMPT = (
    "Du bist der wai-Manager-Agent. Antworte auf Deutsch, knapp und hilfreich. "
    "Wenn du Kundeninformationen brauchst, nutze die verfügbaren Werkzeuge. "
    "Fuer CRM-Themen (Kontakte, Accounts, Leads, Deals, Pipelines, Interaktionen) "
    "delegiere an das Tool 'sales_support'."
)
MAX_TOOL_ROUNDS = 5
PREVIEW_LEN = 240

SALES_SUPPORT_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "sales_support",
        "description": (
            "CRM-Spezialist — delegiere Fragen zu Kontakten, Leads, Deals, "
            "Accounts, Pipelines oder Interaktionen an mich. Parameter: task (str)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Auftrag fuer den sales_support in natuerlicher Sprache.",
                }
            },
            "required": ["task"],
        },
    },
}

def _emit(emitter: EventEmitter | None, event_type: str, **data) -> None:
    if emitter is None:
        return
    emitter.emit(event_type, **data)


def _preview(text: str | None) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= PREVIEW_LEN else text[:PREVIEW_LEN] + "…"


def _usage(resp) -> dict:
    usage = getattr(resp, "usage", None)
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
    }


async def _auto_title(user_message: str, assistant_response: str, emitter: EventEmitter | None = None) -> str:
    """Erzeugt einen kurzen Chat-Titel (3-5 Worte) aus dem ersten Exchange."""
    client = get_client()
    model = get_tier1_model()
    t0 = time.monotonic()
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Du erzeugst einen praegnanten Chat-Titel auf Deutsch — 3 bis 5 "
                    "Woerter, keine Anfuehrungszeichen, kein Punkt am Ende, keine "
                    "Emojis. Antworte NUR mit dem Titel."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User: {user_message[:400]}\n\n"
                    f"Assistant: {assistant_response[:400]}\n\n"
                    "Titel:"
                ),
            },
        ],
        temperature=0.3,
        max_completion_tokens=24,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    raw = (resp.choices[0].message.content or "").strip().strip('"').strip("'")
    raw = raw.splitlines()[0].strip() if raw else ""
    if raw.endswith("."):
        raw = raw[:-1].strip()
    title = raw[:80] or "Neue Konversation"
    _emit(emitter, "chat_title_generated", title=title, model=model, duration_ms=duration_ms, **_usage(resp))
    return title


def _maybe_update_chat_title(chat_id: int, tenant_slug: str, new_title: str) -> bool:
    """Setzt den Chat-Titel, wenn er noch der Default ('Neuer Chat ...') ist."""
    with session_for_tenant(tenant_slug) as s:
        chat = s.get(AiChat, chat_id)
        if chat is None or chat.is_deleted:
            return False
        current = (chat.title or "").strip()
        # Default-Titel oder leer ueberschreiben — alles andere unberuehrt lassen
        if current and not current.startswith("Neuer Chat "):
            return False
        chat.title = new_title
        s.commit()
        return True


async def classify_intent(user_message: str, emitter: EventEmitter | None = None) -> str:
    client = get_client()
    model = get_tier1_model()
    t0 = time.monotonic()
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Antworte NUR mit einem Wort: 'lead_management' wenn es um "
                    "Kunden, Leads, Kontakte, Accounts, Deals, Pipelines, "
                    "Interaktionen oder CRM-Themen geht — sonst 'general_chat'."
                ),
            },
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_completion_tokens=10,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    intent = (resp.choices[0].message.content or "general_chat").strip().lower()
    _emit(emitter, "intent_classified", intent=intent, model=model, duration_ms=duration_ms, **_usage(resp))
    return intent


def _to_openai_tools(mcp_tools: list) -> list[dict]:
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}}
        for t in mcp_tools
    ]


async def _dispatch_tool_call(
    session: ClientSession,
    name: str,
    args: dict,
    *,
    parent_emitter: EventEmitter,
    parent_chat_id: int,
) -> tuple[str, bool]:
    """sales_support läuft als Sub-Agent (Plan 02), alles andere als MCP-Tool. Gibt (text, is_error)."""
    try:
        if name == "sales_support":
            task = str(args.get("task") or "").strip()
            tenant_slug = get_tenant() or "demo"
            user_id = get_user() or 0
            return await emit_sub_agent_call(
                parent_emitter=parent_emitter,
                role="sales_support",
                parent_chat_id=parent_chat_id,
                parent_tool_call_id=0,  # AiToolCall-Row existiert erst nach _persist_exchange
                tenant_slug=tenant_slug,
                user_id=user_id,
                task=task,
                fn=run_sales_support,
            )
        result = await session.call_tool(name, args)
        return " ".join(c.text for c in result.content if hasattr(c, "text")), False
    except Exception as exc:
        log.warning("tool_call_failed name=%s error=%s", name, exc)
        return f"Tool-Fehler: {exc!r}", True


async def _stream_completion(
    *,
    model: str,
    messages: list,
    tools: list[dict] | None,
    emitter: EventEmitter | None,
    round_idx: int,
) -> tuple[str, list[dict], dict]:
    """Async-streamt eine Chat-Completion und aggregiert Content + Tool-Calls.

    Emittiert pro Text-Chunk ein 'llm_delta'-Event (volatile, nicht persistiert).
    Liefert (content, tool_calls_openai_style, usage_dict).
    """
    client = get_client()
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        kwargs["tools"] = tools

    stream = await client.chat.completions.create(**kwargs)
    content_parts: list[str] = []
    # Akku fuer Tool-Calls (per index sammeln, da Argumente fragmentiert kommen)
    tool_acc: dict[int, dict] = {}
    usage: dict = {"prompt_tokens": None, "completion_tokens": None}

    async for chunk in stream:
        chunk_usage = getattr(chunk, "usage", None)
        if chunk_usage is not None:
            usage["prompt_tokens"] = getattr(chunk_usage, "prompt_tokens", None)
            usage["completion_tokens"] = getattr(chunk_usage, "completion_tokens", None)
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if getattr(delta, "content", None):
            content_parts.append(delta.content)
            _emit(emitter, "llm_delta", round=round_idx, content_delta=delta.content)
        tcs = getattr(delta, "tool_calls", None) or []
        for tc in tcs:
            slot = tool_acc.setdefault(
                tc.index, {"id": "", "type": "function", "name": "", "arguments": ""}
            )
            if getattr(tc, "id", None):
                slot["id"] = tc.id
            fn = getattr(tc, "function", None)
            if fn is not None:
                if getattr(fn, "name", None):
                    slot["name"] += fn.name
                if getattr(fn, "arguments", None):
                    slot["arguments"] += fn.arguments

    tool_calls_out = [
        {
            "id": slot["id"],
            "type": slot["type"],
            "function": {"name": slot["name"], "arguments": slot["arguments"] or "{}"},
        }
        for _idx, slot in sorted(tool_acc.items())
        if slot["name"]
    ]
    return "".join(content_parts), tool_calls_out, usage


async def _run_tool_round(
    session: ClientSession,
    messages: list,
    tools: list[dict],
    emitter: EventEmitter | None,
    round_idx: int,
    *,
    chat_id: int,
) -> tuple[list[dict], list[dict]]:
    model = get_tier2_model()

    _emit(emitter, "llm_request", model=model, messages_count=len(messages), has_tools=bool(tools), round=round_idx)
    t0 = time.monotonic()
    content, tool_calls, usage = await _stream_completion(
        model=model, messages=messages, tools=tools, emitter=emitter, round_idx=round_idx,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit(
        emitter,
        "llm_response",
        model=model,
        duration_ms=duration_ms,
        has_tool_calls=bool(tool_calls),
        content_preview=_preview(content),
        round=round_idx,
        **usage,
    )

    if not tool_calls:
        return messages + [{"role": "assistant", "content": content or ""}], []

    msg = {
        "role": "assistant",
        "content": content,
        "tool_calls": tool_calls,
    }
    messages.append(msg)

    round_summary: list[dict] = []
    for tc in tool_calls:
        fn = tc.get("function") or {}
        name = fn.get("name") or ""
        call_id = tc.get("id") or ""
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        _emit(emitter, "tool_call_started", tool_name=name, call_id=call_id, args=args)
        t_tool = time.monotonic()
        if name == "sales_support" and emitter is None:
            # Sub-Agent-Spawn braucht den Parent-Emitter für Lifecycle-Events.
            text, is_error = "Tool-Fehler: sub_agent_spawn_ohne_emitter", True
        else:
            text, is_error = await _dispatch_tool_call(
                session, name, args,
                parent_emitter=emitter,  # type: ignore[arg-type]
                parent_chat_id=chat_id,
            )
        tool_duration_ms = int((time.monotonic() - t_tool) * 1000)
        _emit(
            emitter,
            "tool_call_result",
            tool_name=name,
            call_id=call_id,
            duration_ms=tool_duration_ms,
            result_preview=_preview(text),
            is_error=is_error,
        )
        messages.append({"role": "tool", "tool_call_id": call_id, "content": text})
        round_summary.append({"name": name, "args": args})

    return messages, round_summary


async def _handle_general_chat(messages: list, emitter: EventEmitter | None) -> str:
    model = get_tier2_model()
    _emit(emitter, "llm_request", model=model, messages_count=len(messages), has_tools=False, round=0)
    t0 = time.monotonic()
    content, _tool_calls, usage = await _stream_completion(
        model=model, messages=messages, tools=None, emitter=emitter, round_idx=0,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit(
        emitter,
        "llm_response",
        model=model,
        duration_ms=duration_ms,
        has_tool_calls=False,
        content_preview=_preview(content),
        round=0,
        **usage,
    )
    return content


async def _run_tool_loop(
    session: ClientSession,
    messages: list,
    emitter: EventEmitter | None,
    *,
    chat_id: int,
) -> tuple[str, list[dict]]:
    tool_list = (await session.list_tools()).tools
    tools = _to_openai_tools(tool_list)
    tools.append(SALES_SUPPORT_TOOL)
    _emit(
        emitter,
        "mcp_connected",
        url=MCP_LEAD_URL,
        tool_names=[t.name for t in tool_list] + ["sales_support"],
    )
    summary: list[dict] = []
    for i in range(MAX_TOOL_ROUNDS):
        messages, round_summary = await _run_tool_round(
            session, messages, tools, emitter, round_idx=i + 1, chat_id=chat_id,
        )
        summary.extend(round_summary)
        last = messages[-1]
        if last["role"] == "assistant" and not last.get("tool_calls"):
            break
    return messages[-1].get("content", ""), summary


async def _handle_lead_chat(
    messages: list,
    emitter: EventEmitter | None,
    *,
    chat_id: int,
) -> tuple[str, list[dict]]:
    try:
        async with sse_client(url=MCP_LEAD_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return await _run_tool_loop(session, messages, emitter, chat_id=chat_id)
    except (ConnectionRefusedError, OSError) as exc:
        log.warning("mcp_unreachable url=%s error=%s", MCP_LEAD_URL, exc)
        _emit(emitter, "error", error_type="mcp_unreachable", message=str(exc))
        return "Der Kundendaten-Server ist aktuell nicht erreichbar. Bitte später erneut versuchen.", []


async def chat(
    chat_id: int,
    user_message: str,
    tenant_slug: str,
    user_id: int,
    emitter: EventEmitter | None = None,
) -> dict:
    set_actor("ai", "manager")
    if not user_message or not user_message.strip():
        return {"response": "Bitte gib eine Nachricht ein.", "tool_calls": [], "duration_ms": 0, "intent": ""}

    # Existenz und Zugehoerigkeit pruefen
    with session_for_tenant(tenant_slug) as s:
        ai_chat = s.get(AiChat, chat_id)
        if ai_chat is None or ai_chat.is_deleted:
            raise ValueError(f"AiChat {chat_id} nicht gefunden")
        if not (ai_chat.is_shared or ai_chat.user_id == user_id):
            raise PermissionError(f"User {user_id} darf AiChat {chat_id} nicht beschreiben")

    started = time.monotonic()
    history = load_history(chat_id, tenant_slug)
    log.info(
        "chat.start tenant=%s chat_id=%d user_id=%d user_msg=%r history_len=%d",
        tenant_slug, chat_id, user_id, user_message, len(history),
    )
    _emit(
        emitter,
        "trace_started",
        tenant_id=tenant_slug,
        chat_id=chat_id,
        user_id=user_id,
        user_message=user_message,
        history_len=len(history),
    )

    intent = await classify_intent(user_message, emitter)
    log.info("chat.intent tenant=%s intent=%s", tenant_slug, intent)

    base_messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    base_messages.extend(history)
    base_messages.append({"role": "user", "content": user_message})
    new_msg_start_index = len(base_messages)
    messages = base_messages

    if intent != "lead_management":
        answer = await _handle_general_chat(messages, emitter)
        messages = messages + [{"role": "assistant", "content": answer}]
        tool_calls_summary: list[dict] = []
    else:
        answer, tool_calls_summary = await _handle_lead_chat(messages, emitter, chat_id=chat_id)

    new_messages = messages[new_msg_start_index:]

    try:
        persist_exchange(chat_id, tenant_slug, user_message, new_messages)
    except Exception:  # noqa: BLE001 — persistence-fail darf den Response nicht killen
        log.exception("persist_exchange_failed chat_id=%d", chat_id)

    # Erste Antwort -> automatischer Titel. Nur ausloesen, wenn keine History vor diesem
    # Exchange existierte (i.e. dies war die erste User-Message des Chats).
    if not history and answer and answer.strip():
        try:
            new_title = await _auto_title(user_message, answer, emitter)
            await asyncio.to_thread(_maybe_update_chat_title, chat_id, tenant_slug, new_title)
        except Exception:  # noqa: BLE001 — Titel-Fail darf den Response nicht killen
            log.exception("auto_title_failed chat_id=%d", chat_id)

    duration_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "chat.done tenant=%s chat_id=%d response=%r duration_ms=%d tools=%s",
        tenant_slug, chat_id, answer, duration_ms, tool_calls_summary,
    )
    _emit(emitter, "trace_completed", response=answer, total_duration_ms=duration_ms, status="ok")
    return {
        "response": answer,
        "tool_calls": tool_calls_summary,
        "duration_ms": duration_ms,
        "intent": intent,
        "chat_id": chat_id,
    }
