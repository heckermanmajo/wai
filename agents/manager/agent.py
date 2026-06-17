"""Manager-Agent — Top-Level-Orchestrator (Skeleton-Version).

Erste Version: nimmt Chat-History entgegen, ruft GPT-5.5 auf und kann ein
einzelnes Mock-MCP-Tool (`get_time`) per OpenAI-Function-Calling nutzen.
Single-Round Tool-Use: Modell darf max. 1× tools aufrufen, danach folgt
direkt die finale Antwort.

Wird vom Gateway via `chat(history, user_message)` aufgerufen. Sync, weil
das OpenAI-SDK sync ist — Gateway wrappt mit asyncio.to_thread.
"""
import json
import os
import time

import httpx

from lib.logging import get_logger
from agents.manager.provider import MODEL, get_client

log = get_logger(__name__)

MCP_MOCK_URL = os.environ.get("MCP_MOCK_URL", "http://mcp_mock:8000")

SYSTEM_PROMPT = (
    "Du bist der wai-Manager-Agent. Antworte auf Deutsch, knapp und hilfreich. "
    "Wenn der User nach der aktuellen Uhrzeit oder dem aktuellen Datum fragt, "
    "nutze das Tool 'get_time' statt zu raten."
)


def _tool_definitions() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "Holt die aktuelle Server-Zeit über den Mock-MCP-Server.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def _call_mcp_tool(name: str, arguments: dict) -> str:
    """Ruft das Mock-MCP per HTTP auf und gibt das Ergebnis als JSON-String zurück."""
    url = f"{MCP_MOCK_URL}/call_tool"
    log.info("mcp.call tool=%s url=%s args=%r", name, url, arguments)
    with httpx.Client(timeout=10.0) as cx:
        resp = cx.post(url, json={"name": name, "arguments": arguments})
        resp.raise_for_status()
        data = resp.json()
    log.info("mcp.result tool=%s result=%r", name, data)
    return json.dumps(data)


def chat(history: list[dict], user_message: str) -> dict:
    """Verarbeitet eine Chat-Runde.

    history: bereits geführte Nachrichten ({role, content}).
    user_message: neue Nachricht vom User.
    Returns: {response, tool_calls, duration_ms}
    """
    started = time.monotonic()
    client = get_client()

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    log.info("chat.start user_msg=%r history_len=%d", user_message, len(history))

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=_tool_definitions(),
    )
    choice = response.choices[0].message
    tool_calls_summary: list[dict] = []

    if choice.tool_calls:
        messages.append(
            {
                "role": "assistant",
                "content": choice.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.tool_calls
                ],
            }
        )
        for tc in choice.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = _call_mcp_tool(tc.function.name, args)
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )
            tool_calls_summary.append({"name": tc.function.name, "args": args})

        response = client.chat.completions.create(model=MODEL, messages=messages)
        choice = response.choices[0].message

    duration_ms = int((time.monotonic() - started) * 1000)
    answer = choice.content or ""
    log.info(
        "chat.done response=%r duration_ms=%d tool_calls=%s",
        answer,
        duration_ms,
        tool_calls_summary,
    )
    return {
        "response": answer,
        "tool_calls": tool_calls_summary,
        "duration_ms": duration_ms,
    }
