"""Template: Sub-Agent-MCP-Server (Plan 05).

Kopieren als ``agents/<role>/server.py`` und ``<role>`` ueberall ersetzen.
Zusaetzlich:
1. ``agents/<role>/agent.py`` muss ``run_<role>(task, *, sub_emitter,
   sub_trace_uid, sub_chat_id, tenant_slug, user_id) -> str`` definieren.
2. ``docker-compose.yml`` um einen Service erweitern (Service-Name = `<role>`,
   intern Port 8001, extern naechster freier ab 8504).
3. ``lib/agent.MCP_ENDPOINTS`` um ``("<role>", "http://<role>:8001/sse")``
   erweitern.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

# from agents.<role>.agent import run_<role>  # noqa: E501  — Konkretisieren beim Kopieren
from lib.events import EventEmitter
from lib.logging import get_logger
from lib.tenant_context import set_actor, set_tenant, set_trace_uid

logger = get_logger(__name__)

ROLE = "<role>"  # eindeutiger Sub-Agent-Identifier (= MCP-Tool-Name)
mcp = FastMCP(f"wai-{ROLE}", host="0.0.0.0", port=8001)

MCP_VERSION = "0.1.0"


@mcp.tool()
def manifest() -> dict:
    return {
        "name": f"wai-{ROLE}",
        "version": MCP_VERSION,
        "kind": "sub_agent",
        "description": f"Beschreibung von {ROLE}.",
        "tools": [
            {
                "name": ROLE,
                "kind": "sub_agent",
                "description": f"Sub-Agent-Aufruf {ROLE}. Parameter: task (str).",
            }
        ],
    }


# Hinweis: Beim Kopieren den Decorator-Namen auf den jeweiligen <role>
# umbenennen, damit das Tool unter dem richtigen Namen registriert wird.
@mcp.tool()
async def template_tool(
    task: str,
    tenant_slug: str = "demo",
    sub_trace_uid: str = "",
    sub_chat_id: int = 0,
    user_id: int = 0,
) -> str:
    """Wrapper um run_<role>(...).

    Die Sub-Trace-Klammer setzt der Manager (lib/agent.invoke_sub_agent_via_mcp).
    Hier setzen wir nur den lokalen Tenant-/Actor-/Trace-Context und rufen
    die Agent-Funktion.
    """
    set_tenant(tenant_slug or "demo")
    if sub_trace_uid:
        set_trace_uid(sub_trace_uid)
    set_actor("ai", ROLE)
    emitter = EventEmitter(sub_trace_uid or "mcp-sub-trace",
                           tenant_slug or "demo", task)
    try:
        # return await run_<role>(
        #     task,
        #     sub_emitter=emitter,
        #     sub_trace_uid=emitter.trace_uid,
        #     sub_chat_id=int(sub_chat_id or 0),
        #     tenant_slug=tenant_slug or "demo",
        #     user_id=int(user_id or 0),
        # )
        return f"<replace template_tool with concrete impl for {ROLE}>"
    finally:
        emitter.close()


def _serve() -> None:
    port = int(os.environ.get("PORT", 8001))
    logger.info("Starte %s-MCP auf Port %s via SSE", ROLE, port)
    mcp.run(transport="sse")


if __name__ == "__main__":
    _serve()
