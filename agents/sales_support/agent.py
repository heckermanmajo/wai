"""sales_support-Agent — CRM-Spezialist (Sub-Agent vom Manager).

Verbindet sich via MCP-SSE zum crm_mcp-Server und exposed dessen Tools
(contact_*, account_*, lead_*, deal_*, interaction_log, pipeline_list,
task_create, note_add, comment_add, reminder_create) an gpt-5.5.

Aufruf: ausschließlich über ``lib/agent.emit_sub_agent_call`` (Plan 02).
Der Helper reicht ``sub_emitter`` (für Telemetrie), ``sub_trace_uid``,
``sub_chat_id`` (für Persistenz) und ``tenant_slug``/``user_id`` rein.
Der Sub-Agent persistiert seinen Exchange via ``lib/chat_persist`` in den
Sub-Chat — dadurch ist der gesamte Sub-Trace im Debug-View sichtbar.

Antwortet auf Deutsch. Bei Visualisierungs-Wuenschen gibt der Agent HTML
(Tabellen, Listen, Cards) zurueck, das vom Chat-UI direkt via innerHTML
gerendert wird.
"""
from __future__ import annotations

import json
import os
import time

from mcp import ClientSession
from mcp.client.sse import sse_client

from agents.manager.provider import get_client, get_tier2_model
from lib.chat_persist import persist_exchange
from lib.events import EventEmitter
from lib.logging import get_logger

log = get_logger(__name__)

MCP_CRM_URL = os.environ.get("MCP_CRM_URL", "http://crm_mcp:8001/sse")
MAX_TOOL_ROUNDS = 5
PREVIEW_LEN = 240

SYSTEM_PROMPT = (
    "Du bist sales_support, ein spezialisierter CRM-Assistent fuer "
    "Vertriebsmitarbeiter. Du hast Zugriff auf das CRM (Contacts, Accounts, "
    "Leads, Deals, Interactions, Pipelines). Antworte auf Deutsch. "
    "Wenn der Nutzer Daten visualisieren will, GIB HTML zurueck — Tabellen "
    "(<table>), Listen, kleine Cards. Inline-styles erlaubt.\n\n"
    "WICHTIG — Entity-Links: Wenn du Contacts, Accounts, Leads oder Deals "
    "im HTML erwaehnst (Name, Titel, Tabellenzeile), wrappe den anklickbaren "
    "Text IMMER in ein <a>-Tag mit data-entity und data-id:\n"
    "  <a class=\"entity-link\" data-entity=\"contact\" data-id=\"42\">Maria Mueller</a>\n"
    "Erlaubte data-entity-Werte: contact, account, lead, deal. Verwende "
    "ausschliesslich die echten id-Werte aus den Tool-Ergebnissen — nichts "
    "erfinden. Bei einer Liste/Tabelle wird mindestens der Namens-/Titel-Spaltenwert "
    "so verlinkt, damit der Nutzer per Klick die Detail-Ansicht oeffnen kann."
)


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


def _to_openai_tools(mcp_tools: list) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema,
            },
        }
        for t in mcp_tools
    ]


def _build_tool_call_msg(tc) -> dict:
    return {
        "id": tc.id,
        "type": tc.type,
        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
    }


async def _run_tool_round(
    session: ClientSession,
    messages: list,
    tools: list[dict],
    emitter: EventEmitter,
    round_idx: int,
) -> list[dict]:
    client = get_client()
    model = get_tier2_model()
    emitter.emit("llm_request", model=model, messages_count=len(messages), has_tools=bool(tools), round=round_idx)
    t0 = time.monotonic()
    resp = await client.chat.completions.create(model=model, messages=messages, tools=tools)
    duration_ms = int((time.monotonic() - t0) * 1000)
    choice = resp.choices[0].message
    emitter.emit(
        "llm_response",
        model=model,
        duration_ms=duration_ms,
        has_tool_calls=bool(choice.tool_calls),
        content_preview=_preview(choice.content),
        round=round_idx,
        **_usage(resp),
    )

    if not choice.tool_calls:
        return messages + [{"role": "assistant", "content": choice.content or ""}]

    msg = {
        "role": "assistant",
        "content": choice.content,
        "tool_calls": [_build_tool_call_msg(tc) for tc in choice.tool_calls],
    }
    messages.append(msg)
    for tc in choice.tool_calls:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        emitter.emit("tool_call_started", tool_name=tc.function.name, call_id=tc.id, args=args)
        t_tool = time.monotonic()
        is_error = False
        try:
            result = await session.call_tool(tc.function.name, args)
            text = " ".join(c.text for c in result.content if hasattr(c, "text"))
        except Exception as exc:  # noqa: BLE001
            log.warning("crm_tool_failed name=%s error=%s", tc.function.name, exc)
            text = f"Tool-Fehler: {exc!r}"
            is_error = True
        tool_duration_ms = int((time.monotonic() - t_tool) * 1000)
        emitter.emit(
            "tool_call_result",
            tool_name=tc.function.name,
            call_id=tc.id,
            duration_ms=tool_duration_ms,
            result_preview=_preview(text),
            is_error=is_error,
        )
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
    return messages


async def _run_tool_loop(session: ClientSession, messages: list, emitter: EventEmitter) -> str:
    tool_list = (await session.list_tools()).tools
    tools = _to_openai_tools(tool_list)
    emitter.emit("mcp_connected", url=MCP_CRM_URL, tool_names=[t.name for t in tool_list])
    for i in range(MAX_TOOL_ROUNDS):
        messages = await _run_tool_round(session, messages, tools, emitter, round_idx=i + 1)
        last = messages[-1]
        if last["role"] == "assistant" and not last.get("tool_calls"):
            return last.get("content", "") or ""
    return messages[-1].get("content", "") or ""


async def run_sales_support(
    task: str,
    *,
    sub_emitter: EventEmitter,
    sub_trace_uid: str,
    sub_chat_id: int,
    tenant_slug: str,
    user_id: int,
) -> str:
    """Fuehrt einen sales_support-Task gegen das CRM-MCP aus.

    Wird ausschliesslich über ``lib/agent.emit_sub_agent_call`` aufgerufen.
    Der Sub-Trace (logging_db) wird im Helper geklammert; hier emittieren
    wir die regulären Lifecycle-Events (mcp_connected, llm_request, ...)
    auf dem Sub-Emitter und persistieren den Exchange in den Sub-Chat.

    ``user_id`` ist aktuell nur Audit-Pass-Through (für künftige Felder).
    """
    del user_id  # nicht benötigt, aber Signatur stabil für emit_sub_agent_call

    if not task or not task.strip():
        return "Bitte gib einen Auftrag fuer den sales_support an."
    log.info(
        "sales_support.start tenant=%s sub_chat_id=%d sub_trace_uid=%s task=%r",
        tenant_slug, sub_chat_id, sub_trace_uid, task,
    )
    sub_emitter.emit(
        "trace_started",
        tenant_id=tenant_slug,
        chat_id=sub_chat_id,
        user_message=task,
        history_len=0,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"[Mandant: {tenant_slug}]\n\n{task}",
        },
    ]
    new_msg_start = len(messages)

    started = time.monotonic()
    answer = ""
    try:
        async with sse_client(url=MCP_CRM_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                answer = await _run_tool_loop(session, messages, sub_emitter)
    except (ConnectionRefusedError, OSError) as exc:
        log.warning("crm_mcp_unreachable url=%s error=%s", MCP_CRM_URL, exc)
        sub_emitter.emit("error", error_type="mcp_unreachable", message=str(exc))
        answer = (
            "Der CRM-Server ist aktuell nicht erreichbar. "
            "Bitte spaeter erneut versuchen."
        )
        # Sicherstellen, dass die Antwort als Assistant-Message in den Persist-Pfad fliesst
        messages.append({"role": "assistant", "content": answer})

    duration_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "sales_support.done tenant=%s sub_chat_id=%d response_len=%d duration_ms=%d",
        tenant_slug, sub_chat_id, len(answer), duration_ms,
    )

    new_messages = messages[new_msg_start:]
    try:
        persist_exchange(sub_chat_id, tenant_slug, task, new_messages)
    except Exception:  # noqa: BLE001 — Persist-Fail darf das Result nicht killen
        log.exception("sub_persist_failed sub_chat_id=%d", sub_chat_id)

    sub_emitter.emit("trace_completed", response=answer, total_duration_ms=duration_ms, status="ok")
    return answer
