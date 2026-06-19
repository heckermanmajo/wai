"""HTML-UI fuer das Chat-Interface mit Tabs (Sessions / Mappe / Werkzeuge).

Wird gerendert unter /<tenant-slug>/. Bindet den Tenant-Slug als
window.WAI_TENANT-Konstante ein, alle Backend-Calls gehen ueber
/<slug>/... Routen. Live-Trace-Events kommen via SSE wie zuvor.

Drei Sidebar-Tabs:
    Sessions  — eigene und geteilte AiChats; neuer Chat; klonen; teilen
    Mappe     — Files / CRM-Entities / Tasks-Notes-Comments / Tool-Calls
                pro aktiver Session
    Werkzeuge — bestehende Tools/Mock-Kunden/Beispiel-Prompts (read-only)
"""
from html import escape


def render_chat(tenant_slug: str, username: str, display_name: str) -> str:
    safe_slug = escape(tenant_slug)
    safe_user = escape(display_name or username)
    return _CHAT_HTML.replace("__TENANT__", safe_slug).replace("__USER__", safe_user)


_CHAT_HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<title>wai · chat · __TENANT__</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    font: 14px/1.5 -apple-system, system-ui, sans-serif;
    margin: 0; background: #0e0f12; color: #e8eaed; height: 100vh;
    display: flex; flex-direction: column;
  }
  header {
    padding: 12px 18px; border-bottom: 1px solid #25262b; font-weight: 600;
    display: flex; justify-content: space-between; align-items: center;
  }
  header small { color: #7c818b; font-weight: 400; margin-left: 6px; }
  .header-right { display: flex; align-items: center; gap: 12px; font-size: 12px; }
  .header-right .user { color: #9aa0aa; font-family: ui-monospace, monospace; }
  .header-right .user b { color: #cfe1ff; font-weight: 600; }
  .nav-link {
    color: #82b1ff; text-decoration: none; font-size: 12px; font-weight: 500;
    font-family: ui-monospace, monospace;
  }
  .nav-link:hover { color: #cfe1ff; text-decoration: underline; }
  #debugToggle { padding: 0 10px; height: 30px; font-size: 14px; background: #2d2f36; color: #e8eaed; border: none; border-radius: 6px; cursor: pointer; }
  body.debug-collapsed #debugPanel { display: none; }

  #layout { flex: 1; display: flex; min-height: 0; }
  #chat { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  #log { flex: 1; overflow-y: auto; padding: 18px; }
  .msg {
    max-width: 720px; margin: 0 auto 14px; padding: 10px 14px; border-radius: 8px;
    white-space: pre-wrap; word-wrap: break-word;
  }
  .msg.user { background: #1f2532; color: #cfe1ff; }
  .msg.assistant { background: #1a1c20; color: #e8eaed; }
  .assistant-bubble table { border-collapse: collapse; margin: 8px 0 }
  .assistant-bubble th, .assistant-bubble td { border: 1px solid #444; padding: 6px 10px }
  .assistant-bubble th { background: #2a2c30 }
  .msg.tool {
    background: #221d12; color: #f0c674;
    font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px;
  }
  .msg.error { background: #2a1818; color: #f08080; }
  .role { font-size: 11px; text-transform: uppercase; opacity: 0.6; margin-bottom: 4px; letter-spacing: 0.05em; }
  form#form { display: flex; gap: 8px; padding: 12px 18px; border-top: 1px solid #25262b; background: #131418; align-items: flex-end; }
  textarea {
    flex: 1; resize: none; padding: 10px; border-radius: 6px;
    border: 1px solid #2d2f36; background: #1a1c20; color: #e8eaed; font: inherit;
    min-height: 40px; max-height: 140px;
  }
  button {
    padding: 0 18px; height: 40px; border: none; border-radius: 6px;
    background: #4669ff; color: white; font-weight: 600; cursor: pointer;
  }
  button.icon {
    padding: 0 12px; background: #2d2f36; color: #e8eaed;
  }
  button.icon:hover { background: #3a3d46; }
  button.recording { background: #b94343; color: white; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .uploaded-img { max-width: 360px; max-height: 240px; border-radius: 6px; margin-top: 6px; display: block; }
  .upload-info { color: #7c818b; font-size: 11px; margin-top: 4px; }
  .entity-link {
    color: #82b1ff; text-decoration: underline dotted;
    cursor: pointer; font-weight: 500;
  }
  .entity-link:hover { color: #cfe1ff; text-decoration-style: solid; }

  /* ----- Sidebar (Tabs) ----- */
  #sidebar {
    width: 320px; border-right: 1px solid #25262b; background: #0c0d10;
    display: flex; flex-direction: column; min-width: 0;
  }
  .tabbar { display: flex; border-bottom: 1px solid #1c1d22; }
  .tabbtn {
    flex: 1; padding: 10px 4px; background: transparent; border: none;
    color: #7c818b; font: inherit; font-size: 12px; font-weight: 600;
    cursor: pointer; text-transform: uppercase; letter-spacing: 0.06em;
    border-bottom: 2px solid transparent;
  }
  .tabbtn:hover { color: #cfe1ff; background: #14161a; }
  .tabbtn.active { color: #cfe1ff; border-bottom-color: #4669ff; }
  .tabbody { flex: 1; overflow-y: auto; padding: 12px; }
  .tabbody.hidden { display: none; }
  .section-h {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em;
    color: #7c818b; margin: 16px 0 6px; font-weight: 600;
  }
  .section-h:first-child { margin-top: 0; }

  /* Sessions-Tab */
  .new-chat-btn {
    width: 100%; padding: 8px; border: 1px dashed #4669ff;
    background: transparent; color: #82b1ff; font-weight: 600;
    border-radius: 6px; cursor: pointer; margin-bottom: 12px;
  }
  .new-chat-btn:hover { background: #1a1d28; }
  .session-item {
    background: #16181d; border: 1px solid #23262d; border-radius: 6px;
    padding: 8px 10px; margin-bottom: 6px; cursor: pointer;
    position: relative; font-size: 12px;
  }
  .session-item:hover { border-color: #3a3d46; }
  .session-item.active { border-color: #4669ff; background: #1a1d28; }
  .session-item .title { font-weight: 600; color: #e8eaed; margin-bottom: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .session-item .meta { color: #7c818b; font-size: 10px; font-family: ui-monospace, monospace; display: flex; gap: 6px; flex-wrap: wrap; }
  .session-item .meta .badge { background: #2d2f36; color: #cfe1ff; padding: 1px 5px; border-radius: 3px; font-size: 9px; text-transform: uppercase; }
  .session-item .meta .badge.shared { background: #1d3a2a; color: #7ed99c; }
  .session-item .meta .badge.foreign { background: #3a2a1d; color: #f0c674; }
  .session-actions { display: none; gap: 4px; margin-top: 6px; }
  .session-item.active .session-actions { display: flex; }
  .session-actions button {
    flex: 1; height: 24px; padding: 0 6px; font-size: 10px;
    background: #2d2f36; color: #cfe1ff; border-radius: 4px;
    font-weight: 500; border: none; cursor: pointer;
  }
  .session-actions button:hover { background: #3a3d46; }
  .session-actions .danger { color: #f4a4a4; }

  /* Mappe-Tab */
  .mappe-empty { color: #5a5d65; font-style: italic; font-size: 12px; padding: 18px 0; text-align: center; }
  .artifact-card {
    background: #16181d; border: 1px solid #23262d; border-radius: 6px;
    padding: 8px 10px; margin-bottom: 6px; font-size: 12px;
  }
  .artifact-card .title { font-weight: 600; color: #e8eaed; }
  .artifact-card .meta { color: #7c818b; font-size: 10px; font-family: ui-monospace, monospace; margin-top: 2px; }
  .artifact-card.clickable { cursor: pointer; }
  .artifact-card.clickable:hover { border-color: #4669ff; }
  .artifact-card .rel { float: right; color: #82b1ff; font-size: 9px; text-transform: uppercase; }
  .toolcall-card {
    background: #221d12; border: 1px solid #3a2f1f; border-radius: 6px;
    padding: 6px 8px; margin-bottom: 4px; font-size: 11px;
    font-family: ui-monospace, monospace;
  }
  .toolcall-card .name { color: #f0c674; font-weight: 600; }
  .toolcall-card .args { color: #9aa0aa; font-size: 10px; margin-top: 2px; word-break: break-all; }
  .toolcall-card .result { color: #7ed99c; font-size: 10px; margin-top: 2px; word-break: break-all; max-height: 60px; overflow: hidden; }

  /* Werkzeuge-Tab */
  .tool, .kunde, .beispiel {
    background: #16181d; border: 1px solid #23262d; border-radius: 6px;
    padding: 8px 10px; margin-bottom: 6px; font-size: 12px;
  }
  .tool .name { font-family: ui-monospace, monospace; color: #82b1ff; font-size: 11px; font-weight: 600; }
  .tool .desc { color: #9aa0aa; font-size: 11px; margin-top: 3px; }
  .beispiel { cursor: pointer; }
  .beispiel:hover { border-color: #4669ff; }

  /* Overlays (Entity-Detail + Error) — wie bisher */
  #overlay, #errOverlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.55);
    display: none; align-items: center; justify-content: center; z-index: 100;
  }
  #overlay.open, #errOverlay.open { display: flex; }
  .overlay-card {
    background: #16181d; border: 1px solid #2d2f36; border-radius: 8px;
    max-width: 540px; width: 90%; max-height: 80vh; overflow: auto;
    padding: 18px 22px; box-shadow: 0 12px 40px rgba(0,0,0,0.45);
  }
  .overlay-head {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px; border-bottom: 1px solid #25262b; padding-bottom: 8px;
  }
  .overlay-head .title { font-weight: 600; font-size: 15px; }
  .overlay-head .sub { color: #7c818b; font-family: ui-monospace, monospace; font-size: 11px; margin-left: 8px; }
  .overlay-head button { background: transparent; color: #9aa0aa; padding: 0 8px; height: 28px; font-weight: 400; font-size: 16px; }
  .overlay-head button:hover { color: #e8eaed; }
  .overlay-body table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .overlay-body th, .overlay-body td { border-bottom: 1px solid #23262d; padding: 6px 8px; text-align: left; vertical-align: top; word-break: break-word; }
  .overlay-body th { color: #9aa0aa; font-weight: 500; width: 38%; font-family: ui-monospace, monospace; font-size: 12px; }
  .overlay-body .empty { color: #7c818b; font-style: italic; }
  .overlay-body .err { color: #f08080; }

  /* Debug-Panel (rechte Seite) */
  #debugPanel {
    width: 380px; border-left: 1px solid #25262b; background: #0a0b0e;
    display: flex; flex-direction: column; min-width: 0; font-size: 12px;
  }
  .dbg-head { padding: 12px 14px; border-bottom: 1px solid #1c1d22; display: flex; justify-content: space-between; align-items: center; }
  .dbg-head h2 { margin: 0; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #7c818b; font-weight: 600; }
  .dbg-meta { font-family: ui-monospace, monospace; font-size: 10px; color: #7c818b; display: flex; gap: 8px; align-items: center; }
  .dbg-meta a { color: #82b1ff; text-decoration: none; }
  .dbg-stats { padding: 8px 14px; border-bottom: 1px solid #1c1d22; display: flex; gap: 14px; flex-wrap: wrap; color: #9aa0aa; font-family: ui-monospace, monospace; font-size: 10px; min-height: 14px; }
  .dbg-stats b { color: #e8eaed; font-weight: 600; }
  .dbg-events { flex: 1; overflow-y: auto; padding: 8px 0; }
  .dbg-empty { color: #5a5d65; padding: 18px 14px; font-style: italic; font-size: 11px; }
  .dbg-ev { border-left: 3px solid transparent; padding: 6px 12px 6px 11px; margin-bottom: 1px; font-family: ui-monospace, monospace; font-size: 11px; line-height: 1.4; }
  .dbg-ev:hover { background: #14161a; }
  .dbg-ev .row1 { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
  .dbg-ev .type { font-weight: 600; }
  .dbg-ev .meta { color: #6a6e76; font-size: 10px; }
  .dbg-ev .body { color: #c5cad3; margin-top: 2px; word-break: break-word; }
  .dbg-ev .body code { background: #1a1c20; padding: 1px 4px; border-radius: 3px; color: #cfe1ff; }
  .dbg-ev.t-intent_classified { border-left-color: #82b1ff; } .dbg-ev.t-intent_classified .type { color: #82b1ff; }
  .dbg-ev.t-mcp_connected { border-left-color: #b39ddb; } .dbg-ev.t-mcp_connected .type { color: #b39ddb; }
  .dbg-ev.t-llm_request { border-left-color: #4a5468; } .dbg-ev.t-llm_request .type { color: #8a94a8; }
  .dbg-ev.t-llm_response { border-left-color: #7ed99c; } .dbg-ev.t-llm_response .type { color: #7ed99c; }
  .dbg-ev.t-tool_call_started { border-left-color: #f0c674; } .dbg-ev.t-tool_call_started .type { color: #f0c674; }
  .dbg-ev.t-tool_call_result { border-left-color: #d4a45a; } .dbg-ev.t-tool_call_result .type { color: #d4a45a; }
  .dbg-ev.t-error { border-left-color: #f08080; background: #1d1010; } .dbg-ev.t-error .type { color: #f08080; }
  .dbg-ev.t-trace_completed { border-left-color: #7ed99c; background: #0e1810; } .dbg-ev.t-trace_completed .type { color: #7ed99c; }
</style>
</head>
<body>
<header>
  <span>wai <small>· __TENANT__ · manager-agent</small></span>
  <span class="header-right">
    <span class="user">User: <b>__USER__</b></span>
    <a class="nav-link" href="/__TENANT__/logout">Logout</a>
    <a class="nav-link" href="/traces" target="_blank">/traces ↗</a>
    <button type="button" class="icon" id="debugToggle" title="Debug-Panel umschalten">🐞</button>
  </span>
</header>
<div id="layout">
  <aside id="sidebar">
    <div class="tabbar">
      <button class="tabbtn active" data-tab="sessions">Sessions</button>
      <button class="tabbtn" data-tab="mappe">Mappe</button>
      <button class="tabbtn" data-tab="werkzeuge">Werkzeuge</button>
    </div>
    <div class="tabbody" id="tab-sessions">
      <button class="new-chat-btn" id="newChatBtn">+ Neuer Chat</button>
      <div id="sessionsList"></div>
    </div>
    <div class="tabbody hidden" id="tab-mappe">
      <div class="mappe-empty" id="mappeEmpty">Keine aktive Session.</div>
      <div id="mappeContent" class="hidden">
        <div class="section-h">Files</div>
        <div id="mappeFiles"></div>
        <div class="section-h">CRM-Entities</div>
        <div id="mappeCrm"></div>
        <div class="section-h">Tasks · Notes · Comments</div>
        <div id="mappeTnc"></div>
        <div class="section-h">Tool-Calls</div>
        <div id="mappeTools"></div>
      </div>
    </div>
    <div class="tabbody hidden" id="tab-werkzeuge">
      <div class="section-h">MCP-Tools</div>
      <div id="tools"></div>
      <div class="section-h">Mock-Kunden</div>
      <div id="kunden"></div>
      <div class="section-h">Beispiel-Prompts</div>
      <div id="beispiele"></div>
    </div>
  </aside>
  <div id="chat">
    <div id="log"></div>
    <form id="form">
      <textarea id="input" placeholder="Nachricht an den Manager…" autofocus></textarea>
      <input id="imageInput" type="file" accept="image/*" style="display:none" />
      <button id="imgBtn" class="icon" type="button" title="Bild anhängen">🖼</button>
      <button id="micBtn" class="icon" type="button" title="Sprachaufnahme">🎤</button>
      <button id="send" type="submit">Senden</button>
    </form>
  </div>
  <aside id="debugPanel">
    <div class="dbg-head">
      <h2>Debug · Live-Events</h2>
      <div class="dbg-meta">
        <span id="dbgTraceUid">—</span>
        <a id="dbgTraceLink" href="#" target="_blank" style="display:none">Detail ↗</a>
      </div>
    </div>
    <div class="dbg-stats" id="dbgStats"></div>
    <div class="dbg-events" id="dbgEvents">
      <div class="dbg-empty">Noch keine Anfrage. Sende eine Nachricht — Events erscheinen hier live.</div>
    </div>
  </aside>
</div>
<div id="overlay" role="dialog" aria-modal="true">
  <div class="overlay-card">
    <div class="overlay-head">
      <div><span class="title" id="overlayTitle">Details</span><span class="sub" id="overlaySub"></span></div>
      <button type="button" id="overlayClose" title="Schließen">✕</button>
    </div>
    <div class="overlay-body" id="overlayBody"></div>
  </div>
</div>
<script>
  const TENANT = "__TENANT__";
  const API = (p) => "/" + TENANT + p;
  const log = document.getElementById('log');
  const form = document.getElementById('form');
  const input = document.getElementById('input');
  const send = document.getElementById('send');
  let currentChatId = null;
  let lastUserMessage = '';

  // ---------- helpers ----------
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => (
      {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
    ));
  }
  function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString([], { hour12: false }).replace(',', '');
  }

  function addMsg(role, content) {
    const div = el('div', 'msg ' + role);
    div.appendChild(el('div', 'role', role));
    const body = document.createElement('div');
    if (role === 'assistant') {
      body.className = 'assistant-bubble';
      body.innerHTML = content;
      wireEntityLinks(body);
    } else {
      body.textContent = content;
    }
    div.appendChild(body);
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  // ---------- Tabs ----------
  document.querySelectorAll('.tabbtn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tabbtn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.tabbody').forEach(b => b.classList.add('hidden'));
      document.getElementById('tab-' + btn.dataset.tab).classList.remove('hidden');
      if (btn.dataset.tab === 'mappe') refreshMappe();
    });
  });

  // ---------- Sessions ----------
  async function refreshSessions() {
    try {
      const resp = await fetch(API('/chats'));
      if (!resp.ok) return;
      const data = await resp.json();
      const list = document.getElementById('sessionsList');
      list.innerHTML = '';
      if (!data.chats || !data.chats.length) {
        list.innerHTML = '<div class="mappe-empty">Noch keine Chats.</div>';
        return;
      }
      data.chats.forEach(c => list.appendChild(renderSessionItem(c)));
    } catch (err) {
      console.error('refreshSessions failed', err);
    }
  }

  function renderSessionItem(c) {
    const item = el('div', 'session-item' + (c.id === currentChatId ? ' active' : ''));
    item.dataset.id = c.id;
    const title = el('div', 'title', c.title || ('Chat #' + c.id));
    item.appendChild(title);
    const meta = el('div', 'meta');
    meta.appendChild(el('span', null, '#' + c.id));
    meta.appendChild(el('span', null, fmtDate(c.updated_at)));
    if (c.is_shared) meta.appendChild(el('span', 'badge shared', 'shared'));
    if (!c.is_mine) meta.appendChild(el('span', 'badge foreign', 'fremd'));
    item.appendChild(meta);
    if (c.is_mine) {
      const actions = el('div', 'session-actions');
      const cloneBtn = el('button', null, 'Klonen');
      cloneBtn.addEventListener('click', (e) => { e.stopPropagation(); cloneSession(c.id); });
      actions.appendChild(cloneBtn);
      const shareBtn = el('button', null, c.is_shared ? 'Privat machen' : 'Teilen');
      shareBtn.addEventListener('click', (e) => { e.stopPropagation(); toggleShare(c.id, !c.is_shared); });
      actions.appendChild(shareBtn);
      item.appendChild(actions);
    }
    item.addEventListener('click', () => loadChat(c.id));
    return item;
  }

  async function newChat() {
    try {
      const resp = await fetch(API('/chats'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: '' }),
      });
      if (!resp.ok) return;
      const data = await resp.json();
      await loadChat(data.id);
      await refreshSessions();
    } catch (err) { console.error('newChat failed', err); }
  }
  document.getElementById('newChatBtn').addEventListener('click', newChat);

  async function loadChat(chatId) {
    currentChatId = chatId;
    log.innerHTML = '';
    try {
      const resp = await fetch(API('/chats/' + chatId));
      if (!resp.ok) {
        addMsg('error', 'Konnte Chat nicht laden: ' + resp.status);
        return;
      }
      const data = await resp.json();
      (data.messages || []).forEach(m => {
        if (m.role === 'user' || m.role === 'assistant') {
          addMsg(m.role, m.content || '');
        } else if (m.role === 'tool') {
          addMsg('tool', '← ' + (m.tool_name || m.tool_call_id || '') + ': ' + (m.content || ''));
        }
      });
    } catch (err) {
      addMsg('error', 'Fehler beim Laden: ' + err);
    }
    document.querySelectorAll('.session-item').forEach(it => {
      it.classList.toggle('active', Number(it.dataset.id) === chatId);
    });
    if (!document.getElementById('tab-mappe').classList.contains('hidden')) refreshMappe();
  }

  async function cloneSession(chatId) {
    try {
      const resp = await fetch(API('/chats/' + chatId + '/clone'), { method: 'POST' });
      if (!resp.ok) return;
      const data = await resp.json();
      await refreshSessions();
      await loadChat(data.id);
    } catch (err) { console.error('clone failed', err); }
  }

  async function toggleShare(chatId, share) {
    try {
      await fetch(API('/chats/' + chatId + '/share'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shared: share }),
      });
      await refreshSessions();
    } catch (err) { console.error('share toggle failed', err); }
  }

  // ---------- Mappe ----------
  async function refreshMappe() {
    const empty = document.getElementById('mappeEmpty');
    const content = document.getElementById('mappeContent');
    if (!currentChatId) {
      empty.classList.remove('hidden');
      content.classList.add('hidden');
      return;
    }
    empty.classList.add('hidden');
    content.classList.remove('hidden');
    try {
      const resp = await fetch(API('/chats/' + currentChatId + '/artifacts'));
      if (!resp.ok) return;
      const data = await resp.json();
      renderFiles(data.files || []);
      renderCrm(data.crm_entities || []);
      renderTnc(data.tasks_notes_comments || {});
      renderToolCalls(data.tool_calls || []);
    } catch (err) {
      console.error('mappe failed', err);
    }
  }

  function renderFiles(files) {
    const c = document.getElementById('mappeFiles');
    c.innerHTML = '';
    if (!files.length) { c.innerHTML = '<div class="mappe-empty">keine Files</div>'; return; }
    files.forEach(f => {
      const card = el('div', 'artifact-card');
      const rel = el('span', 'rel', f.relation || '');
      card.appendChild(rel);
      card.appendChild(el('div', 'title', f.filename || ('#' + f.id)));
      card.appendChild(el('div', 'meta', `${f.mime} · ${f.size_bytes} B · ${fmtDate(f.created_at)}`));
      c.appendChild(card);
    });
  }

  function renderCrm(entities) {
    const c = document.getElementById('mappeCrm');
    c.innerHTML = '';
    if (!entities.length) { c.innerHTML = '<div class="mappe-empty">keine CRM-Entities</div>'; return; }
    entities.forEach(e => {
      const card = el('div', 'artifact-card clickable');
      const rel = el('span', 'rel', e.relation || '');
      card.appendChild(rel);
      const shortCls = (e.artifact_cls || '').replace('crm.', '');
      card.appendChild(el('div', 'title', shortCls + ' #' + e.artifact_id));
      card.appendChild(el('div', 'meta', e.artifact_cls));
      card.addEventListener('click', () => openEntityOverlay(shortCls, e.artifact_id, shortCls + ' #' + e.artifact_id));
      c.appendChild(card);
    });
  }

  function renderTnc(tnc) {
    const c = document.getElementById('mappeTnc');
    c.innerHTML = '';
    const groups = [
      ['Tasks', tnc.tasks || []],
      ['Notes', tnc.notes || []],
      ['Comments', tnc.comments || []],
    ];
    let any = false;
    groups.forEach(([name, items]) => {
      if (!items.length) return;
      any = true;
      const head = el('div', 'meta', name);
      head.style.marginTop = '8px';
      c.appendChild(head);
      items.forEach(it => {
        const card = el('div', 'artifact-card');
        card.appendChild(el('div', 'title', it.title || it.body || ('#' + it.id)));
        if (it.body && it.title) card.appendChild(el('div', 'meta', it.body.slice(0, 100)));
        c.appendChild(card);
      });
    });
    if (!any) c.innerHTML = '<div class="mappe-empty">nichts verknüpft</div>';
  }

  function renderToolCalls(calls) {
    const c = document.getElementById('mappeTools');
    c.innerHTML = '';
    if (!calls.length) { c.innerHTML = '<div class="mappe-empty">keine Tool-Aufrufe</div>'; return; }
    calls.forEach(tc => {
      const card = el('div', 'toolcall-card');
      card.appendChild(el('div', 'name', tc.tool_name + ' · ' + tc.duration_ms + 'ms'));
      if (tc.arguments_json) card.appendChild(el('div', 'args', tc.arguments_json));
      if (tc.result_text) card.appendChild(el('div', 'result', tc.result_text.slice(0, 240)));
      c.appendChild(card);
    });
  }

  // ---------- Werkzeuge (read-only) ----------
  async function loadInfo() {
    try {
      const resp = await fetch('/demo/info');
      if (!resp.ok) return;
      const data = await resp.json();
      const toolsDiv = document.getElementById('tools');
      toolsDiv.innerHTML = '';
      (data.tools || []).forEach(t => {
        const card = el('div', 'tool');
        card.appendChild(el('div', 'name', t.name));
        card.appendChild(el('div', 'desc', t.description || ''));
        toolsDiv.appendChild(card);
      });
      const kundenDiv = document.getElementById('kunden');
      kundenDiv.innerHTML = '';
      (data.kunden || []).forEach(k => {
        const card = el('div', 'kunde');
        card.appendChild(el('div', 'name', k.name));
        card.appendChild(el('div', 'desc', k.projekt + ' · ' + k.status));
        kundenDiv.appendChild(card);
      });
      const bspDiv = document.getElementById('beispiele');
      bspDiv.innerHTML = '';
      (data.beispiele || []).forEach(b => {
        const card = el('div', 'beispiel', b);
        card.addEventListener('click', () => { input.value = b; input.focus(); });
        bspDiv.appendChild(card);
      });
    } catch (err) { /* still */ }
  }

  // ---------- Entity-Overlay ----------
  const overlay = document.getElementById('overlay');
  const overlayTitle = document.getElementById('overlayTitle');
  const overlaySub = document.getElementById('overlaySub');
  const overlayBody = document.getElementById('overlayBody');
  const ENTITY_LABEL = { contact: 'Kontakt', account: 'Account', lead: 'Lead', deal: 'Deal' };

  function wireEntityLinks(root) {
    root.querySelectorAll('a.entity-link[data-entity][data-id]').forEach(a => {
      if (a.dataset.bound === '1') return;
      a.dataset.bound = '1';
      a.addEventListener('click', (e) => {
        e.preventDefault();
        openEntityOverlay(a.dataset.entity, a.dataset.id, a.textContent.trim());
      });
    });
  }

  function closeOverlay() { overlay.classList.remove('open'); }
  function renderEntityTable(data) {
    if (!data || typeof data !== 'object') return '<div class="empty">Keine Daten.</div>';
    if (data.error) return `<div class="err">${escapeHtml(data.error)}</div>`;
    const keys = Object.keys(data);
    if (!keys.length) return '<div class="empty">Leer.</div>';
    const rows = keys.map(k => {
      let v = data[k];
      if (v === null || v === undefined || v === '') v = '<span class="empty">—</span>';
      else if (typeof v === 'object') v = `<code>${escapeHtml(JSON.stringify(v))}</code>`;
      else v = escapeHtml(String(v));
      return `<tr><th>${escapeHtml(k)}</th><td>${v}</td></tr>`;
    }).join('');
    return `<table>${rows}</table>`;
  }
  async function openEntityOverlay(cls, id, label) {
    overlayTitle.textContent = (ENTITY_LABEL[cls] || cls) + ' · ' + (label || ('#' + id));
    overlaySub.textContent = `${cls}/${id}`;
    overlayBody.innerHTML = '<div class="empty">Lade…</div>';
    overlay.classList.add('open');
    try {
      const resp = await fetch(API('/entity/' + encodeURIComponent(cls) + '/' + encodeURIComponent(id)));
      if (!resp.ok) { overlayBody.innerHTML = `<div class="err">Fehler ${resp.status}</div>`; return; }
      const payload = await resp.json();
      overlayBody.innerHTML = renderEntityTable(payload.data);
    } catch (err) {
      overlayBody.innerHTML = `<div class="err">${escapeHtml(String(err))}</div>`;
    }
  }
  document.getElementById('overlayClose').addEventListener('click', closeOverlay);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeOverlay(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && overlay.classList.contains('open')) closeOverlay(); });

  // ---------- Debug-Panel ----------
  const dbgEvents = document.getElementById('dbgEvents');
  const dbgStats = document.getElementById('dbgStats');
  const dbgTraceUid = document.getElementById('dbgTraceUid');
  const dbgTraceLink = document.getElementById('dbgTraceLink');
  const dbgToggle = document.getElementById('debugToggle');
  const DBG_KEY = 'wai-debug-collapsed';
  if (localStorage.getItem(DBG_KEY) === '1') document.body.classList.add('debug-collapsed');
  dbgToggle.addEventListener('click', () => {
    document.body.classList.toggle('debug-collapsed');
    localStorage.setItem(DBG_KEY, document.body.classList.contains('debug-collapsed') ? '1' : '0');
  });
  function dbgReset(traceUid) {
    dbgEvents.innerHTML = '';
    if (traceUid) {
      dbgTraceUid.textContent = traceUid.slice(0, 8) + '…';
      dbgTraceLink.href = '/traces#' + encodeURIComponent(traceUid);
      dbgTraceLink.style.display = '';
    } else {
      dbgTraceUid.textContent = '—';
      dbgTraceLink.style.display = 'none';
    }
    dbgStats.innerHTML = '';
  }
  function dbgUpdateStats(stats) {
    dbgStats.innerHTML = '';
    [['Events', stats.events], ['LLM', stats.llm_calls], ['Tools', stats.tool_calls],
     ['Tokens', (stats.tokens_in || 0) + (stats.tokens_out || 0)], ['ms', stats.duration_ms]
    ].forEach(([k, v]) => {
      const span = el('span', null);
      span.innerHTML = `${k} <b>${v != null ? v : '—'}</b>`;
      dbgStats.appendChild(span);
    });
  }
  function dbgAppend(ev) {
    const div = el('div', 'dbg-ev t-' + ev.event_type);
    const row1 = el('div', 'row1');
    row1.appendChild(el('span', 'type', ev.event_type));
    const time = new Date(ev.timestamp).toLocaleTimeString([], { hour12: false });
    row1.appendChild(el('span', 'meta', '#' + ev.sequence + ' · ' + time));
    div.appendChild(row1);
    const body = describeEvent(ev);
    if (body) {
      const bodyEl = el('div', 'body');
      bodyEl.innerHTML = body;
      div.appendChild(bodyEl);
    }
    dbgEvents.appendChild(div);
    dbgEvents.scrollTop = dbgEvents.scrollHeight;
  }
  function describeEvent(ev) {
    const d = ev.data || {};
    const esc = escapeHtml;
    switch (ev.event_type) {
      case 'intent_classified':
        return `intent=<code>${esc(d.intent || '')}</code> · ${d.duration_ms}ms`;
      case 'mcp_connected':
        return `tools=[${(d.tool_names || []).map(esc).join(', ')}]`;
      case 'llm_request':
        return `round=${d.round} msgs=${d.messages_count}`;
      case 'llm_response': {
        const preview = d.content_preview ? `<br><span style="color:#9aa0aa">${esc(d.content_preview)}</span>` : '';
        return `${d.duration_ms}ms${preview}`;
      }
      case 'tool_call_started':
        return `<code>${esc(d.tool_name || '')}</code>(${esc(JSON.stringify(d.args || {}))})`;
      case 'tool_call_result': {
        const preview = d.result_preview ? `<br><span style="color:#9aa0aa">${esc(d.result_preview)}</span>` : '';
        return `<code>${esc(d.tool_name || '')}</code> · ${d.duration_ms}ms${preview}`;
      }
      case 'error': return `<code>${esc(d.error_type || '')}</code> ${esc(d.message || '')}`;
      case 'trace_completed': return `status=<code>${esc(d.status || '')}</code> · ${d.total_duration_ms}ms`;
      default: return esc(JSON.stringify(d));
    }
  }
  function parseSSEBuffer(buffer) {
    const out = [];
    let rest = buffer;
    while (true) {
      const idx = rest.indexOf('\\n\\n');
      if (idx < 0) break;
      const block = rest.slice(0, idx);
      rest = rest.slice(idx + 2);
      let evName = 'message';
      const dataLines = [];
      block.split('\\n').forEach(line => {
        if (line.startsWith('event:')) evName = line.slice(6).trim();
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
      });
      if (dataLines.length) {
        try { out.push({ name: evName, data: JSON.parse(dataLines.join('\\n')) }); } catch (_) {}
      }
    }
    return { events: out, rest };
  }

  // ---------- send ----------
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = input.value.trim();
    if (!msg) return;
    if (!currentChatId) {
      addMsg('error', 'Bitte erst eine Session auswählen oder + Neuer Chat klicken.');
      return;
    }
    addMsg('user', msg);
    lastUserMessage = msg;
    input.value = '';
    send.disabled = true;
    dbgReset(null);
    const stats = { events: 0, llm_calls: 0, tool_calls: 0, tokens_in: 0, tokens_out: 0, duration_ms: null };
    try {
      const resp = await fetch(API('/chats/' + currentChatId + '/messages'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg }),
      });
      if (!resp.ok || !resp.body) {
        addMsg('error', 'Fehler ' + resp.status);
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let final = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const { events, rest } = parseSSEBuffer(buffer);
        buffer = rest;
        for (const sse of events) {
          if (sse.name === 'trace') {
            dbgReset(sse.data.trace_uid);
          } else if (sse.name === 'event') {
            stats.events += 1;
            if (sse.data.event_type === 'llm_response') stats.llm_calls += 1;
            if (sse.data.event_type === 'tool_call_started') stats.tool_calls += 1;
            const d = sse.data.data || {};
            if (d.prompt_tokens) stats.tokens_in += d.prompt_tokens;
            if (d.completion_tokens) stats.tokens_out += d.completion_tokens;
            dbgAppend(sse.data);
            dbgUpdateStats(stats);
          } else if (sse.name === 'done') {
            final = sse.data;
          }
        }
      }
      if (!final) { addMsg('error', 'Stream ohne done-Event'); return; }
      stats.duration_ms = final.duration_ms;
      dbgUpdateStats(stats);
      if (final.status === 'error') addMsg('error', 'Fehler: ' + (final.error_message || 'unbekannt'));
      else addMsg('assistant', final.response);
      await refreshSessions();
      if (!document.getElementById('tab-mappe').classList.contains('hidden')) await refreshMappe();
    } catch (err) {
      addMsg('error', 'Netzwerkfehler: ' + err);
    } finally {
      send.disabled = false;
      input.focus();
    }
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });

  // ---------- Bild-Upload ----------
  const imgBtn = document.getElementById('imgBtn');
  const imageInput = document.getElementById('imageInput');
  imgBtn.addEventListener('click', () => imageInput.click());
  imageInput.addEventListener('change', async () => {
    const file = imageInput.files && imageInput.files[0];
    if (!file) return;
    if (!currentChatId) { addMsg('error', 'Bitte erst Session auswählen'); imageInput.value = ''; return; }
    const fd = new FormData();
    fd.append('file', file);
    addMsg('tool', `→ Bild-Upload: ${file.name}`);
    try {
      const resp = await fetch(API('/ingest/image?chat_id=' + currentChatId), { method: 'POST', body: fd });
      if (!resp.ok) { addMsg('error', 'Upload-Fehler ' + resp.status); return; }
      const data = await resp.json();
      const div = el('div', 'msg assistant');
      div.appendChild(el('div', 'role', 'image'));
      const body = document.createElement('div');
      body.className = 'assistant-bubble';
      const img = document.createElement('img');
      img.className = 'uploaded-img'; img.src = data.presigned_url; img.alt = file.name;
      body.appendChild(img);
      body.appendChild(el('div', 'upload-info', `attachment_id=${data.attachment_id}`));
      div.appendChild(body);
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
      if (!document.getElementById('tab-mappe').classList.contains('hidden')) await refreshMappe();
    } catch (err) { addMsg('error', 'Upload: ' + err); }
    finally { imageInput.value = ''; }
  });

  // ---------- Sprachaufnahme ----------
  const micBtn = document.getElementById('micBtn');
  let mediaRecorder = null;
  let recordedChunks = [];
  let recordingStream = null;
  async function startRecording() {
    if (!navigator.mediaDevices) { addMsg('error', 'MediaRecorder nicht verfügbar'); return; }
    try { recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch (err) { addMsg('error', 'Mikro: ' + err); return; }
    const mimeCandidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', ''];
    let chosen = '';
    for (const m of mimeCandidates) {
      if (!m || (window.MediaRecorder && MediaRecorder.isTypeSupported(m))) { chosen = m; break; }
    }
    recordedChunks = [];
    mediaRecorder = chosen ? new MediaRecorder(recordingStream, { mimeType: chosen }) : new MediaRecorder(recordingStream);
    mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) recordedChunks.push(e.data); };
    mediaRecorder.onstop = onRecordingStop;
    mediaRecorder.start();
    micBtn.classList.add('recording'); micBtn.textContent = '⏹';
  }
  async function stopRecording() {
    if (!mediaRecorder) return;
    mediaRecorder.stop();
    micBtn.classList.remove('recording'); micBtn.textContent = '🎤';
  }
  async function onRecordingStop() {
    if (recordingStream) { recordingStream.getTracks().forEach(t => t.stop()); recordingStream = null; }
    const mime = (mediaRecorder && mediaRecorder.mimeType) || 'audio/webm';
    const blob = new Blob(recordedChunks, { type: mime });
    recordedChunks = []; mediaRecorder = null;
    if (blob.size === 0) { addMsg('error', 'Aufnahme leer'); return; }
    if (!currentChatId) { addMsg('error', 'Bitte erst Session auswählen'); return; }
    const ext = mime.includes('mp4') ? 'mp4' : 'webm';
    const fd = new FormData();
    fd.append('file', blob, 'aufnahme.' + ext);
    addMsg('tool', `→ Transkription läuft (${Math.round(blob.size / 1024)} KB)…`);
    micBtn.disabled = true;
    try {
      const resp = await fetch(API('/ingest/voice?chat_id=' + currentChatId), { method: 'POST', body: fd });
      if (!resp.ok) { addMsg('error', 'Upload ' + resp.status); return; }
      const data = await resp.json();
      if (data.transcribe_error) addMsg('error', 'Transkription: ' + data.transcribe_error);
      if (data.transcript) { input.value = (input.value ? input.value + ' ' : '') + data.transcript; input.focus(); }
      if (!document.getElementById('tab-mappe').classList.contains('hidden')) await refreshMappe();
    } catch (err) { addMsg('error', 'Voice: ' + err); }
    finally { micBtn.disabled = false; }
  }
  micBtn.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') stopRecording();
    else startRecording();
  });

  // ---------- init ----------
  (async () => {
    await loadInfo();
    await refreshSessions();
  })();
</script>
</body>
</html>
"""
