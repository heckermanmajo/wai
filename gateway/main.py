"""wai Gateway — FastAPI entry.

Endpoints:
    GET  /health  → Liveness
    POST /chat    → delegates to manager-agent (async)

Tenant-aware: tenant_id flows through to all downstream services.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lib.logging import setup_logging, get_logger
from agents.manager.agent import chat as manager_chat

setup_logging()
log = get_logger(__name__)

app = FastAPI(title="wai gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    tenant_id: str = Field(default="demo_tenant", description="ID des Handwerksbetriebs")


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict] = []
    duration_ms: int


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=422, detail="message darf nicht leer sein")
    log.info("HTTP /chat tenant=%s user_msg=%r history_len=%d", req.tenant_id, req.message, len(req.history))
    history_dicts = [m.model_dump() for m in req.history]
    try:
        result = await manager_chat(history_dicts, req.message, tenant_id=req.tenant_id)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY fehlt oder Konfigurationsfehler")
    return ChatResponse(**result)
