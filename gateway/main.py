"""wai Gateway — FastAPI-Einstieg.

Endpoints:
    GET  /        → Demo-Chat-UI (inline HTML)
    GET  /health  → Liveness
    POST /chat    → delegiert an manager-Agent

Erste, simple Version: kein Auth, keine DB-Persistenz, keine Sessions.
Frontend hält History stateless und schickt sie bei jedem Call mit.
"""
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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


@app.get("/", response_class=HTMLResponse)
def chat_ui() -> str:
    return _CHAT_HTML


_CHAT_HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<title>wai · chat</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    font: 14px/1.5 -apple-system, system-ui, sans-serif;
    margin: 0; background: #0e0f12; color: #e8eaed; height: 100vh;
    display: flex; flex-direction: column;
  }
  header { padding: 12px 18px; border-bottom: 1px solid #25262b; font-weight: 600; }
  header small { color: #7c818b; font-weight: 400; margin-left: 6px; }
  #log { flex: 1; overflow-y: auto; padding: 18px; }
  .msg {
    max-width: 720px; margin: 0 auto 14px; padding: 10px 14px; border-radius: 8px;
    white-space: pre-wrap; word-wrap: break-word;
  }
  .msg.user { background: #1f2532; color: #cfe1ff; }
  .msg.assistant { background: #1a1c20; color: #e8eaed; }
  .msg.tool {
    background: #221d12; color: #f0c674;
    font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px;
  }
  .msg.error { background: #2a1818; color: #f08080; }
  .role { font-size: 11px; text-transform: uppercase; opacity: 0.6; margin-bottom: 4px; letter-spacing: 0.05em; }
  form { display: flex; gap: 8px; padding: 12px 18px; border-top: 1px solid #25262b; background: #131418; }
  textarea {
    flex: 1; resize: none; padding: 10px; border-radius: 6px;
    border: 1px solid #2d2f36; background: #1a1c20; color: #e8eaed; font: inherit;
    min-height: 40px; max-height: 140px;
  }
  button {
    padding: 0 18px; border: none; border-radius: 6px;
    background: #4669ff; color: white; font-weight: 600; cursor: pointer;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
</head>
<body>
<header>wai <small>· manager-agent · gpt-5.5</small></header>
<div id="log"></div>
<form id="form">
  <textarea id="input" placeholder="Nachricht an den Manager…" autofocus></textarea>
  <button id="send" type="submit">Senden</button>
</form>
<script>
  const log = document.getElementById('log');
  const form = document.getElementById('form');
  const input = document.getElementById('input');
  const send = document.getElementById('send');
  const history = [];

  function addMsg(role, content) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    const r = document.createElement('div');
    r.className = 'role';
    r.textContent = role;
    div.appendChild(r);
    const c = document.createElement('div');
    c.textContent = content;
    div.appendChild(c);
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = input.value.trim();
    if (!msg) return;
    addMsg('user', msg);
    input.value = '';
    send.disabled = true;
    try {
      const resp = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history }),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        addMsg('error', `Fehler ${resp.status}: ${detail}`);
        return;
      }
      const data = await resp.json();
      if (data.tool_calls && data.tool_calls.length) {
        addMsg('tool', 'tools: ' + data.tool_calls.map(t => t.name).join(', '));
      }
      addMsg('assistant', data.response);
      history.push({ role: 'user', content: msg });
      history.push({ role: 'assistant', content: data.response });
    } catch (err) {
      addMsg('error', String(err));
    } finally {
      send.disabled = false;
      input.focus();
    }
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
</script>
</body>
</html>
"""
