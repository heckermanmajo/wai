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
import json
import os
import time

from mcp import ClientSession
from mcp.client.sse import sse_client
from sqlalchemy import select

from agents.manager.provider import get_client, get_tier1_model, get_tier2_model
from agents.sales_support.agent import run_sales_support
from lib.db import session_for_tenant
from lib.entities.tenant import AiChat, AiMessage, AiToolCall, ChatArtifact
from lib.events import EventEmitter
from lib.logging import get_logger
from lib.tenant_context import get_tenant

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

# Tool-Name → (artifact_cls, arg_field_for_id_or_None, relation)
# arg_field=None bedeutet: ID aus dem JSON-Result lesen (Feld "id").
CRM_TOOL_ARTIFACT_MAP: dict[str, tuple[str, str | None, str]] = {
    "contact_get": ("crm.contact", "id", "touched"),
    "contact_upsert": ("crm.contact", None, "created"),
    "account_get": ("crm.account", "id", "touched"),
    "account_upsert": ("crm.account", None, "created"),
    "lead_get": ("crm.lead", "id", "touched"),
    "lead_create": ("crm.lead", None, "created"),
    "lead_convert": ("crm.lead", "lead_id", "touched"),
    "deal_get": ("crm.deal", "id", "touched"),
    "deal_create": ("crm.deal", None, "created"),
    "deal_advance_stage": ("crm.deal", "deal_id", "touched"),
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


def _load_history(chat_id: int, tenant_slug: str) -> list[dict]:
    """Laedt alle bisherigen Messages eines Chats als OpenAI-style dicts."""
    with session_for_tenant(tenant_slug) as s:
        rows = list(
            s.scalars(
                select(AiMessage)
                .where(AiMessage.chat_id == chat_id, AiMessage.is_deleted.is_(False))
                .order_by(AiMessage.id)
            )
        )
        tool_call_rows = list(
            s.scalars(
                select(AiToolCall)
                .where(
                    AiToolCall.message_id.in_([r.id for r in rows]) if rows else False,
                    AiToolCall.is_deleted.is_(False),
                )
                .order_by(AiToolCall.id)
            )
        ) if rows else []

    calls_by_msg: dict[int, list[AiToolCall]] = {}
    for tc in tool_call_rows:
        calls_by_msg.setdefault(tc.message_id, []).append(tc)

    history: list[dict] = []
    for m in rows:
        if m.role == "tool":
            history.append({
                "role": "tool",
                "tool_call_id": m.tool_call_id,
                "content": m.content,
            })
        elif m.role == "assistant":
            tcs = calls_by_msg.get(m.id, [])
            if tcs:
                history.append({
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": tc.tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tc.tool_name,
                                "arguments": tc.arguments_json or "{}",
                            },
                        }
                        for tc in tcs
                    ],
                })
            else:
                history.append({"role": "assistant", "content": m.content})
        else:
            history.append({"role": m.role, "content": m.content})
    return history


def _extract_artifact(tool_name: str, args: dict, result_text: str) -> tuple[str, int, str] | None:
    spec = CRM_TOOL_ARTIFACT_MAP.get(tool_name)
    if spec is None:
        return None
    artifact_cls, arg_field, relation = spec
    artifact_id: int | None = None
    if arg_field is not None:
        raw = args.get(arg_field)
        if isinstance(raw, (int, str)) and str(raw).strip().isdigit():
            artifact_id = int(raw)
    if artifact_id is None and result_text:
        try:
            data = json.loads(result_text)
        except (json.JSONDecodeError, ValueError):
            data = None
        if isinstance(data, dict):
            cand = data.get("id")
            if isinstance(cand, int):
                artifact_id = cand
            elif isinstance(cand, str) and cand.isdigit():
                artifact_id = int(cand)
    if artifact_id is None or artifact_id <= 0:
        return None
    return (artifact_cls, artifact_id, relation)


def _persist_exchange(
    chat_id: int,
    tenant_slug: str,
    user_message: str,
    new_messages: list[dict],
) -> None:
    """Schreibt User-Message + alle vom Agent erzeugten Messages + ToolCalls in die DB.

    new_messages: alle Eintraege ab der vom Agent erzeugten User-Message
    (system + history werden NICHT mit uebergeben — Caller schneidet ab).
    """
    with session_for_tenant(tenant_slug) as s:
        seen_artifact_keys: set[tuple[str, int]] = set()
        existing_artifacts = s.scalars(
            select(ChatArtifact).where(
                ChatArtifact.chat_id == chat_id,
                ChatArtifact.is_deleted.is_(False),
            )
        )
        for ea in existing_artifacts:
            seen_artifact_keys.add((ea.artifact_cls, ea.artifact_id))

        s.add(AiMessage(chat_id=chat_id, role="user", content=user_message))
        s.flush()

        assistant_msg_id: int | None = None
        pending_tool_calls: dict[str, AiToolCall] = {}

        for entry in new_messages:
            role = entry.get("role")
            if role == "user":
                continue  # bereits oben persistiert
            if role == "assistant":
                content = entry.get("content") or ""
                tcs = entry.get("tool_calls") or []
                am = AiMessage(chat_id=chat_id, role="assistant", content=content)
                s.add(am)
                s.flush()
                assistant_msg_id = am.id
                pending_tool_calls = {}
                for tc in tcs:
                    fn = tc.get("function") or {}
                    tc_row = AiToolCall(
                        message_id=assistant_msg_id,
                        tool_call_id=str(tc.get("id") or ""),
                        tool_name=str(fn.get("name") or ""),
                        arguments_json=str(fn.get("arguments") or "{}"),
                        result_text="",
                        status="pending",
                        duration_ms=0,
                    )
                    s.add(tc_row)
                    pending_tool_calls[tc_row.tool_call_id] = tc_row
                s.flush()
            elif role == "tool":
                tc_id = str(entry.get("tool_call_id") or "")
                content = entry.get("content") or ""
                tc_row = pending_tool_calls.get(tc_id)
                if tc_row is not None:
                    tc_row.result_text = content
                    tc_row.status = "ok"
                s.add(AiMessage(
                    chat_id=chat_id,
                    role="tool",
                    content=content,
                    tool_call_id=tc_id,
                    tool_name=tc_row.tool_name if tc_row else "",
                ))
                if tc_row is not None:
                    try:
                        args = json.loads(tc_row.arguments_json or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    found = _extract_artifact(tc_row.tool_name, args, content)
                    if found is not None:
                        cls_, aid, rel = found
                        if (cls_, aid) not in seen_artifact_keys:
                            s.add(ChatArtifact(
                                chat_id=chat_id,
                                artifact_cls=cls_,
                                artifact_id=aid,
                                relation=rel,
                            ))
                            seen_artifact_keys.add((cls_, aid))

        s.commit()


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


def _build_tool_call_msg(tc) -> dict:
    return {"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}


async def _dispatch_tool_call(session: ClientSession, name: str, args: dict) -> tuple[str, bool]:
    """sales_support läuft als Sub-Agent, alles andere als MCP-Tool. Gibt (text, is_error)."""
    try:
        if name == "sales_support":
            task = str(args.get("task") or "").strip()
            tenant_slug = get_tenant() or "demo"
            return await run_sales_support(task, tenant_slug=tenant_slug), False
        result = await session.call_tool(name, args)
        return " ".join(c.text for c in result.content if hasattr(c, "text")), False
    except Exception as exc:
        log.warning("tool_call_failed name=%s error=%s", name, exc)
        return f"Tool-Fehler: {exc!r}", True


async def _run_tool_round(
    session: ClientSession,
    messages: list,
    tools: list[dict],
    emitter: EventEmitter | None,
    round_idx: int,
) -> tuple[list[dict], list[dict]]:
    client = get_client()
    model = get_tier2_model()

    _emit(emitter, "llm_request", model=model, messages_count=len(messages), has_tools=bool(tools), round=round_idx)
    t0 = time.monotonic()
    resp = await client.chat.completions.create(model=model, messages=messages, tools=tools)
    duration_ms = int((time.monotonic() - t0) * 1000)
    choice = resp.choices[0].message
    _emit(
        emitter,
        "llm_response",
        model=model,
        duration_ms=duration_ms,
        has_tool_calls=bool(choice.tool_calls),
        content_preview=_preview(choice.content),
        round=round_idx,
        **_usage(resp),
    )

    if not choice.tool_calls:
        return messages + [{"role": "assistant", "content": choice.content or ""}], []

    msg = {
        "role": "assistant",
        "content": choice.content,
        "tool_calls": [_build_tool_call_msg(tc) for tc in choice.tool_calls],
    }
    messages.append(msg)

    round_summary: list[dict] = []
    for tc in choice.tool_calls:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        _emit(emitter, "tool_call_started", tool_name=tc.function.name, call_id=tc.id, args=args)
        t_tool = time.monotonic()
        text, is_error = await _dispatch_tool_call(session, tc.function.name, args)
        tool_duration_ms = int((time.monotonic() - t_tool) * 1000)
        _emit(
            emitter,
            "tool_call_result",
            tool_name=tc.function.name,
            call_id=tc.id,
            duration_ms=tool_duration_ms,
            result_preview=_preview(text),
            is_error=is_error,
        )
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
        round_summary.append({"name": tc.function.name, "args": args})

    return messages, round_summary


async def _handle_general_chat(messages: list, emitter: EventEmitter | None) -> str:
    client = get_client()
    model = get_tier2_model()
    _emit(emitter, "llm_request", model=model, messages_count=len(messages), has_tools=False, round=0)
    t0 = time.monotonic()
    resp = await client.chat.completions.create(model=model, messages=messages)
    duration_ms = int((time.monotonic() - t0) * 1000)
    content = resp.choices[0].message.content or ""
    _emit(
        emitter,
        "llm_response",
        model=model,
        duration_ms=duration_ms,
        has_tool_calls=False,
        content_preview=_preview(content),
        round=0,
        **_usage(resp),
    )
    return content


async def _run_tool_loop(
    session: ClientSession,
    messages: list,
    emitter: EventEmitter | None,
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
        messages, round_summary = await _run_tool_round(session, messages, tools, emitter, round_idx=i + 1)
        summary.extend(round_summary)
        last = messages[-1]
        if last["role"] == "assistant" and not last.get("tool_calls"):
            break
    return messages[-1].get("content", ""), summary


async def _handle_lead_chat(messages: list, emitter: EventEmitter | None) -> tuple[str, list[dict]]:
    try:
        async with sse_client(url=MCP_LEAD_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return await _run_tool_loop(session, messages, emitter)
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
    history = _load_history(chat_id, tenant_slug)
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
        answer, tool_calls_summary = await _handle_lead_chat(messages, emitter)

    new_messages = messages[new_msg_start_index:]

    try:
        _persist_exchange(chat_id, tenant_slug, user_message, new_messages)
    except Exception:  # noqa: BLE001 — persistence-fail darf den Response nicht killen
        log.exception("persist_exchange_failed chat_id=%d", chat_id)

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
