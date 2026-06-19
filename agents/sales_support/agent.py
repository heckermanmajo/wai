"""sales_support-Agent — CRM-Spezialist.

Verbindet sich via MCP-SSE zum crm_mcp-Server und exposed dessen Tools
(contact_*, account_*, lead_*, deal_*, interaction_log, pipeline_list,
task_create, note_add, comment_add, reminder_create) an gpt-5.5.

Wird vom Manager-Agent als Tool aufgerufen (Sub-Agent-Pattern). Die
Tool-Call-Schleife laeuft maximal MAX_TOOL_ROUNDS Runden und gibt am Ende
den finalen assistant-content zurueck.

Antwortet auf Deutsch. Bei Visualisierungs-Wuenschen gibt der Agent HTML
(Tabellen, Listen, Cards) zurueck, das vom Chat-UI direkt via innerHTML
gerendert wird.
"""
from __future__ import annotations

import json
import os

from mcp import ClientSession
from mcp.client.sse import sse_client

from agents.manager.provider import get_client, get_tier2_model
from lib.logging import get_logger

log = get_logger(__name__)

MCP_CRM_URL = os.environ.get("MCP_CRM_URL", "http://crm_mcp:8001/sse")
MAX_TOOL_ROUNDS = 5

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
    session: ClientSession, messages: list, tools: list[dict]
) -> list[dict]:
    client = get_client()
    resp = await client.chat.completions.create(
        model=get_tier2_model(), messages=messages, tools=tools
    )
    choice = resp.choices[0].message
    if not choice.tool_calls:
        return messages + [{"role": "assistant", "content": choice.content or ""}]
    msg = {
        "role": "assistant",
        "content": choice.content,
        "tool_calls": [_build_tool_call_msg(tc) for tc in choice.tool_calls],
    }
    messages.append(msg)
    for tc in choice.tool_calls:
        args = json.loads(tc.function.arguments or "{}")
        result = await session.call_tool(tc.function.name, args)
        text = " ".join(c.text for c in result.content if hasattr(c, "text"))
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
    return messages


async def _run_tool_loop(session: ClientSession, messages: list) -> str:
    tools = _to_openai_tools((await session.list_tools()).tools)
    for _ in range(MAX_TOOL_ROUNDS):
        messages = await _run_tool_round(session, messages, tools)
        last = messages[-1]
        if last["role"] == "assistant" and not last.get("tool_calls"):
            return last.get("content", "") or ""
    return messages[-1].get("content", "") or ""


async def run_sales_support(task: str, tenant_slug: str = "demo") -> str:
    """Fuehrt einen sales_support-Task gegen das CRM-MCP aus.

    task         freier Auftrag in natuerlicher Sprache
    tenant_slug  aktiver Mandant (informativ — der CRM-MCP-Container
                 nutzt WAI_TENANT_SLUG_DEFAULT)
    """
    if not task or not task.strip():
        return "Bitte gib einen Auftrag fuer den sales_support an."
    log.info("sales_support.start tenant=%s task=%r", tenant_slug, task)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"[Mandant: {tenant_slug}]\n\n{task}",
        },
    ]
    try:
        async with sse_client(url=MCP_CRM_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                answer = await _run_tool_loop(session, messages)
                log.info(
                    "sales_support.done tenant=%s response_len=%d",
                    tenant_slug,
                    len(answer),
                )
                return answer
    except (ConnectionRefusedError, OSError) as exc:
        log.warning("crm_mcp_unreachable url=%s error=%s", MCP_CRM_URL, exc)
        return (
            "Der CRM-Server ist aktuell nicht erreichbar. "
            "Bitte spaeter erneut versuchen."
        )


class SalesSupportAgent:
    """Thin OO-Wrapper um run_sales_support fuer Aufrufer, die ein
    Agent-Objekt erwarten. Beide Aufruf-Stile sind explizit unterstuetzt."""

    def __init__(self, tenant_slug: str = "demo") -> None:
        self.tenant_slug = tenant_slug

    async def run(self, task: str) -> str:
        return await run_sales_support(task, tenant_slug=self.tenant_slug)
