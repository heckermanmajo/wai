"""wai Gateway — FastAPI entry.

Endpoints:
    GET  /           → Demo-Chat-UI (inline HTML)
    GET  /health     → Liveness
    GET  /demo/info  → Tool- und Mock-Kunden-Übersicht für das Demo-UI
    POST /chat       → delegates to manager-agent (async)

Tenant-aware: tenant_id flows through to all downstream services.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from lib.logging import setup_logging, get_logger
from agents.manager.agent import chat as manager_chat
from mcp_servers.mock_mcp.data import BEISPIEL_PROMPTS, KUNDEN_DB, TOOLS

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


@app.get("/demo/info")
def demo_info() -> dict:
    kunden = [
        {
            "name": name.title(),
            "projekt": d["projekt"],
            "status": d["status"],
            "rechnung_offen": d["rechnung_offen"],
            "notizen": d["notizen"],
        }
        for name, d in KUNDEN_DB.items()
    ]
    return {"tools": TOOLS, "kunden": kunden, "beispiele": BEISPIEL_PROMPTS}


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
  #layout { flex: 1; display: flex; min-height: 0; }
  aside {
    width: 320px; border-right: 1px solid #25262b; background: #0c0d10;
    overflow-y: auto; padding: 14px; font-size: 13px;
  }
  aside section { margin-bottom: 22px; }
  aside h2 {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em;
    color: #7c818b; margin: 0 0 8px; font-weight: 600;
  }
  .tool, .kunde, .beispiel {
    background: #16181d; border: 1px solid #23262d; border-radius: 6px;
    padding: 8px 10px; margin-bottom: 6px;
  }
  .tool .name {
    font-family: ui-monospace, SFMono-Regular, monospace;
    color: #82b1ff; font-size: 12px; font-weight: 600;
  }
  .tool .desc { color: #c5cad3; margin-top: 3px; font-size: 12px; }
  .tool .params {
    color: #7c818b; font-family: ui-monospace, monospace;
    font-size: 11px; margin-top: 4px;
  }
  .kunde .name { font-weight: 600; color: #e8eaed; }
  .kunde .meta { color: #9aa0aa; font-size: 12px; margin-top: 2px; }
  .badge {
    display: inline-block; padding: 1px 6px; border-radius: 3px;
    font-size: 10px; margin-left: 4px;
  }
  .badge.offen { background: #3a1f1f; color: #f08080; }
  .badge.bezahlt { background: #1f3a26; color: #7ed99c; }
  .beispiel { cursor: pointer; color: #c5cad3; }
  .beispiel:hover { background: #1c1f25; border-color: #4669ff; color: #cfe1ff; }
  #chat { flex: 1; display: flex; flex-direction: column; min-width: 0; }
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
<header>wai <small>· manager-agent · lead-manager-mock</small></header>
<div id="layout">
  <aside>
    <section>
      <h2>Verfügbare MCP-Tools</h2>
      <div id="tools"></div>
    </section>
    <section>
      <h2>Mock-Kunden</h2>
      <div id="kunden"></div>
    </section>
    <section>
      <h2>Beispiel-Prompts (Klick zum Übernehmen)</h2>
      <div id="beispiele"></div>
    </section>
  </aside>
  <div id="chat">
    <div id="log"></div>
    <form id="form">
      <textarea id="input" placeholder="Nachricht an den Manager…" autofocus></textarea>
      <button id="send" type="submit">Senden</button>
    </form>
  </div>
</div>
<script>
  const log = document.getElementById('log');
  const form = document.getElementById('form');
  const input = document.getElementById('input');
  const send = document.getElementById('send');
  const toolsEl = document.getElementById('tools');
  const kundenEl = document.getElementById('kunden');
  const beispieleEl = document.getElementById('beispiele');
  const history = [];

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function renderSidebar(info) {
    info.tools.forEach(t => {
      const box = el('div', 'tool');
      box.appendChild(el('div', 'name', t.name));
      box.appendChild(el('div', 'desc', t.beschreibung));
      const params = t.parameter.map(p => `${p.name}: ${p.typ}`).join(', ');
      box.appendChild(el('div', 'params', `(${params || '—'})`));
      toolsEl.appendChild(box);
    });
    info.kunden.forEach(k => {
      const box = el('div', 'kunde');
      box.appendChild(el('div', 'name', k.name));
      const meta = el('div', 'meta');
      meta.textContent = `${k.projekt} · ${k.status}`;
      const badge = el('span', 'badge ' + (k.rechnung_offen ? 'offen' : 'bezahlt'),
                       k.rechnung_offen ? 'Rechnung offen' : 'bezahlt');
      meta.appendChild(badge);
      box.appendChild(meta);
      kundenEl.appendChild(box);
    });
    info.beispiele.forEach(b => {
      const box = el('div', 'beispiel', b);
      box.addEventListener('click', () => {
        input.value = b;
        input.focus();
      });
      beispieleEl.appendChild(box);
    });
  }

  async function loadInfo() {
    try {
      const resp = await fetch('/demo/info');
      if (!resp.ok) return;
      renderSidebar(await resp.json());
    } catch (e) { /* ignore */ }
  }

  function addMsg(role, content) {
    const div = el('div', 'msg ' + role);
    div.appendChild(el('div', 'role', role));
    div.appendChild(el('div', null, content));
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function describeToolCall(tc) {
    const args = tc.args && Object.keys(tc.args).length
      ? ' ' + JSON.stringify(tc.args)
      : '';
    return `→ ${tc.name}${args}`;
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
      (data.tool_calls || []).forEach(tc => addMsg('tool', describeToolCall(tc)));
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

  loadInfo();
</script>
</body>
</html>
"""
