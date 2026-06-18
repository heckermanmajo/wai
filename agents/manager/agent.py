"""Manager-Agent — async orchestrator with dynamic MCP tool loading.

Two-tier LLM: Tier1 (gpt-4o-mini) for intent classification,
Tier2 (gpt-4o) for reasoning and tool-calling.
MCP connection via SSE ClientSession (not HTTP stub).
"""
import json
import os
import time

from mcp import ClientSession
from mcp.client.sse import sse_client

from agents.manager.provider import get_client, get_tier1_model, get_tier2_model
from lib.logging import get_logger

log = get_logger(__name__)

MCP_LEAD_URL = os.environ.get("MCP_LEAD_URL", "http://localhost:8001/sse")
SYSTEM_PROMPT = (
    "Du bist der wai-Manager-Agent. Antworte auf Deutsch, knapp und hilfreich. "
    "Wenn du Kundeninformationen brauchst, nutze die verfügbaren Werkzeuge."
)
MAX_TOOL_ROUNDS = 5


async def classify_intent(user_message: str) -> str:
    client = get_client()
    resp = await client.chat.completions.create(
        model=get_tier1_model(),
        messages=[
            {"role": "system", "content": "Antworte NUR mit einem Wort: 'lead_management' oder 'general_chat'."},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=10,
    )
    return (resp.choices[0].message.content or "general_chat").strip().lower()


def _to_openai_tools(mcp_tools: list) -> list[dict]:
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}}
        for t in mcp_tools
    ]


def _build_tool_call_msg(tc) -> dict:
    return {"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}


async def _run_tool_round(session: ClientSession, messages: list, tools: list[dict]) -> list[dict]:
    client = get_client()
    resp = await client.chat.completions.create(model=get_tier2_model(), messages=messages, tools=tools)
    choice = resp.choices[0].message
    if not choice.tool_calls:
        return messages + [{"role": "assistant", "content": choice.content or ""}]
    msg = {"role": "assistant", "content": choice.content, "tool_calls": [_build_tool_call_msg(tc) for tc in choice.tool_calls]}
    messages.append(msg)
    for tc in choice.tool_calls:
        args = json.loads(tc.function.arguments or "{}")
        result = await session.call_tool(tc.function.name, args)
        text = " ".join(c.text for c in result.content if hasattr(c, "text"))
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
    return messages


async def _handle_general_chat(messages: list) -> str:
    client = get_client()
    resp = await client.chat.completions.create(model=get_tier2_model(), messages=messages)
    return resp.choices[0].message.content or ""


async def _run_tool_loop(session: ClientSession, messages: list) -> tuple[str, list[dict]]:
    tools = _to_openai_tools((await session.list_tools()).tools)
    summary: list[dict] = []
    for _ in range(MAX_TOOL_ROUNDS):
        prev = len(messages)
        messages = await _run_tool_round(session, messages, tools)
        summary.extend(
            {"name": m.get("tool_call_id", "?"), "args": {}}
            for m in messages[prev:] if m.get("role") == "tool"
        )
        last = messages[-1]
        if last["role"] == "assistant" and not last.get("tool_calls"):
            break
    return messages[-1].get("content", ""), summary


async def _handle_lead_chat(messages: list) -> tuple[str, list[dict]]:
    try:
        async with sse_client(url=MCP_LEAD_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return await _run_tool_loop(session, messages)
    except (ConnectionRefusedError, OSError) as exc:
        log.warning("mcp_unreachable url=%s error=%s", MCP_LEAD_URL, exc)
        return "Der Kundendaten-Server ist aktuell nicht erreichbar. Bitte später erneut versuchen.", []


async def chat(history: list[dict], user_message: str, tenant_id: str = "demo_tenant") -> dict:
    if not user_message or not user_message.strip():
        return {"response": "Bitte gib eine Nachricht ein.", "tool_calls": [], "duration_ms": 0}
    started = time.monotonic()
    log.info("chat.start tenant=%s user_msg=%r history_len=%d", tenant_id, user_message, len(history))
    intent = await classify_intent(user_message)
    log.info("chat.intent tenant=%s intent=%s", tenant_id, intent)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    if intent != "lead_management":
        answer = await _handle_general_chat(messages)
        duration = int((time.monotonic() - started) * 1000)
        log.info("chat.done tenant=%s response=%r duration_ms=%d", tenant_id, answer, duration)
        return {"response": answer, "tool_calls": [], "duration_ms": duration}
    answer, tool_calls_summary = await _handle_lead_chat(messages)
    duration_ms = int((time.monotonic() - started) * 1000)
    log.info("chat.done tenant=%s response=%r duration_ms=%d tools=%s", tenant_id, answer, duration_ms, tool_calls_summary)
    return {"response": answer, "tool_calls": tool_calls_summary, "duration_ms": duration_ms}
