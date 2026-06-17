"""wai Gateway — FastAPI-Einstieg.

Endpoints:
    GET  /health  → Liveness
    POST /chat    → delegiert an manager-Agent

Erste, simple Version: kein Auth, keine DB-Persistenz, keine Sessions.
Frontend hält History stateless und schickt sie bei jedem Call mit.
"""
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict] = []
    duration_ms: int


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    log.info("HTTP /chat user_msg=%r history_len=%d", req.message, len(req.history))
    history_dicts = [m.model_dump() for m in req.history]
    try:
        result = await asyncio.to_thread(manager_chat, history_dicts, req.message)
    except RuntimeError as e:
        log.warning("HTTP /chat config_error=%s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        log.exception("HTTP /chat unexpected_error")
        raise HTTPException(status_code=500, detail="Interner Fehler im Manager-Agent")
    return ChatResponse(**result)


