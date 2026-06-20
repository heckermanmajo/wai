"""sales_support — FastMCP-SSE-Server (Plan 05).

Sub-Agent als eigener Prozess + SSE-Endpunkt. Das `sales_support`-Tool ist
ein dünner Wrapper, der die bestehende ``run_sales_support``-Funktion in
``agents.sales_support.agent`` aufruft.

Wichtig:
- Tool-Aufrufer ist der Manager-Agent. Der Manager hat seinen eigenen
  Trace-Context (Sub-Trace-Klammer via ``lib/agent.emit_sub_agent_call``).
  Wenn der MCP-Tool-Pfad aktiv ist, müssen ``sub_emitter`` & Co. dort her
  kommen — der MCP-Server stellt sie hier per Kontext-Bridge nach.

In dieser Iteration wird der MCP-Pfad **nur** vom Manager benutzt, der
``invoke_sub_agent_via_mcp`` (lib/agent.py) ruft. Dieser Helper läuft die
``emit_sub_agent_call``-Mechanik und ruft dann den MCP-Tool-Endpunkt.
Damit `run_sales_support` lokal im selben Prozess der Sub-Agent-Container-
Instanz ausgeführt werden kann, akzeptiert das MCP-Tool die kompletten
Lifecycle-Felder vom Caller (sub_trace_uid etc.).

Vereinfachung in V1: wir liefern eine Kurzfassung — Tool ``sales_support``
nimmt ``task`` (und optional ``tenant_slug``) entgegen und ruft eine
**vereinfachte** Variante, die ohne Sub-Trace-Klammer auskommt. Die echte
Klammer setzt der Manager über ``lib/agent.invoke_sub_agent_via_mcp``,
indem er die Lifecycle-Events emittiert und den Sub-MCP-Tool-Call dazwischen
schiebt. Sub-Trace-UID wird als Argument durchgereicht.
"""
from __future__ import annotations

import asyncio
import os

from mcp.server.fastmcp import FastMCP

from agents.sales_support.agent import run_sales_support
from lib.events import EventEmitter
from lib.logging import get_logger
from lib.tenant_context import set_actor, set_tenant, set_trace_uid

logger = get_logger(__name__)

mcp = FastMCP("wai-sales-support", host="0.0.0.0", port=8001)

MCP_VERSION = "0.1.0"


@mcp.tool()
def manifest() -> dict:
    """Plan 05 — Self-Description. kind="sub_agent": Tool-Call -> Sub-Chat."""
    return {
        "name": "wai-sales-support",
        "version": MCP_VERSION,
        "kind": "sub_agent",
        "description": (
            "CRM-Spezialist — delegiere Fragen zu Kontakten, Leads, Deals, "
            "Accounts, Pipelines oder Interaktionen an mich."
        ),
        "tools": [
            {
                "name": "sales_support",
                "kind": "sub_agent",
                "description": "Sub-Agent-Aufruf. Parameter: task (str).",
            }
        ],
    }


@mcp.tool()
async def sales_support(
    task: str,
    tenant_slug: str = "demo",
    sub_trace_uid: str = "",
    sub_chat_id: int = 0,
    user_id: int = 0,
) -> str:
    """Sub-Agent-Tool: fuehrt einen sales_support-Task aus.

    In V1 wird ein neuer ``EventEmitter`` lokal erzeugt, weil der Sub-Agent
    in einem eigenen Prozess laeuft und keinen Live-Stream zurueck zum
    Manager hat. Telemetrie wird trotzdem korrekt unter ``sub_trace_uid``
    persistiert (Trace-Forwarder im Gateway), sobald wir den Cross-Process-
    Stream einbauen. Plan 05 dokumentiert das als bewussten Schnitt.
    """
    if not task or not task.strip():
        return "Bitte gib einen Auftrag fuer den sales_support an."

    set_tenant(tenant_slug or "demo")
    if sub_trace_uid:
        set_trace_uid(sub_trace_uid)
    set_actor("ai", "sales_support")

    local_uid = sub_trace_uid or "mcp-sub-trace"
    emitter = EventEmitter(local_uid, tenant_slug or "demo", task)
    try:
        result = await run_sales_support(
            task,
            sub_emitter=emitter,
            sub_trace_uid=local_uid,
            sub_chat_id=int(sub_chat_id or 0),
            tenant_slug=tenant_slug or "demo",
            user_id=int(user_id or 0),
        )
    finally:
        emitter.close()
    return result


def _serve() -> None:
    port = int(os.environ.get("PORT", 8001))
    logger.info("Starte sales_support-MCP auf Port %s via SSE", port)
    mcp.run(transport="sse")


if __name__ == "__main__":
    _serve()
