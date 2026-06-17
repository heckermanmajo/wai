"""Mock-MCP-Server — HTTP-Stub mit MCP-ähnlichen Endpoints.

Kein echtes MCP-Protokoll (kein JSON-RPC, kein stdio) — stattdessen ein
einfacher FastAPI-Service der das Konzept "Tool-Manifest + Tool-Aufruf"
in HTTP nachzeichnet. Reicht als starting point, bis ein echter MCP-Stack
eingezogen wird.

Endpoints:
    GET  /list_tools  → Tool-Manifest
    POST /call_tool   → {name, arguments} → {result}

Aktuelles Tool:
    get_time — aktuelles UTC-Datum/-Uhrzeit (ISO-8601)
"""
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from lib.logging import setup_logging, get_logger

setup_logging()
log = get_logger(__name__)

app = FastAPI(title="wai mock-mcp", version="0.1.0")


class CallToolRequest(BaseModel):
    name: str
    arguments: dict = {}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "wai-mock-mcp", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/list_tools")
def list_tools() -> dict:
    return {
        "tools": [
            {
                "name": "get_time",
                "description": "Gibt die aktuelle UTC-Zeit zurück (ISO-8601).",
                "parameters": {"type": "object", "properties": {}},
            }
        ]
    }


@app.post("/call_tool")
def call_tool(req: CallToolRequest) -> dict:
    log.info("call_tool name=%s args=%r", req.name, req.arguments)
    if req.name == "get_time":
        now = datetime.now(timezone.utc).isoformat()
        return {"result": {"now": now}}
    log.warning("call_tool unknown tool=%s", req.name)
    raise HTTPException(status_code=404, detail=f"Unbekanntes Tool: {req.name}")
