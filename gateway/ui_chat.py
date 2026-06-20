"""HTML-UI fuer das Chat-Interface.

Wird gerendert unter /<tenant-slug>/. Bindet den Tenant-Slug als
window.WAI_TENANT-Konstante ein, alle Backend-Calls gehen ueber
/<slug>/... Routen. Live-Trace-Events kommen via SSE wie zuvor.

Sidebar-Tabs:
    Sessions   — eigene und geteilte AiChats; neuer Chat; klonen; teilen
    Mappe      — Files / CRM-Entities / Tasks-Notes-Comments / Tool-Calls
                 pro aktiver Session
    Dokumente  — globale Document-Liste mit Suche und Inline-Editor
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
<script src="https://cdn.jsdelivr.net/npm/marked@11.1.1/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.8/dist/purify.min.js"></script>
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
    max-width: 75%; padding: 10px 14px; border-radius: 8px;
    white-space: pre-wrap; word-wrap: break-word;
    margin-bottom: 14px;
  }
  /* User rechts (mit linkem Abstand), Assistant links (mit rechtem Abstand) */
  .msg.user {
    background: #1f2532; color: #cfe1ff;
    margin-left: auto; margin-right: 0;
    border-bottom-right-radius: 2px;
  }
  .msg.assistant {
    background: #1a1c20; color: #e8eaed;
    margin-left: 0; margin-right: auto;
    border-bottom-left-radius: 2px;
  }
  /* Tool-/Error-/Image-Hinweise weiter mittig — sind keine "echten" Chat-Bubbles */
  .msg.tool, .msg.error { margin-left: auto; margin-right: auto; max-width: 720px; }
  /* Markdown-Rendering im Assistant-Bubble: dunkle Variante */
  .assistant-bubble { white-space: normal; }
  .assistant-bubble > *:first-child { margin-top: 0; }
  .assistant-bubble > *:last-child { margin-bottom: 0; }
  .assistant-bubble p { margin: 0.5em 0; }
  .assistant-bubble h1, .assistant-bubble h2, .assistant-bubble h3,
  .assistant-bubble h4, .assistant-bubble h5, .assistant-bubble h6 {
    margin: 0.8em 0 0.4em; line-height: 1.25; color: #f1f3f5;
  }
  .assistant-bubble h1 { font-size: 1.35em; }
  .assistant-bubble h2 { font-size: 1.2em; }
  .assistant-bubble h3 { font-size: 1.1em; }
  .assistant-bubble h4, .assistant-bubble h5, .assistant-bubble h6 { font-size: 1em; }
  .assistant-bubble ul, .assistant-bubble ol { margin: 0.4em 0; padding-left: 1.6em; }
  .assistant-bubble li { margin: 0.15em 0; }
  .assistant-bubble li > p { margin: 0.2em 0; }
  .assistant-bubble blockquote {
    margin: 0.5em 0; padding: 4px 12px; border-left: 3px solid #4669ff;
    color: #b8bdc6; background: #131620;
  }
  .assistant-bubble code {
    background: #0c0d10; color: #f0c674; padding: 1px 5px; border-radius: 3px;
    font-family: ui-monospace, "SF Mono", monospace; font-size: 0.92em;
  }
  .assistant-bubble pre {
    background: #0c0d10; color: #e8eaed; padding: 10px 12px; border-radius: 6px;
    border: 1px solid #23262d; overflow-x: auto; margin: 0.6em 0;
    font-family: ui-monospace, "SF Mono", monospace; font-size: 12px; line-height: 1.5;
  }
  .assistant-bubble pre code { background: transparent; color: inherit; padding: 0; font-size: inherit; }
  .assistant-bubble a { color: #82b1ff; text-decoration: underline dotted; }
  .assistant-bubble a:hover { text-decoration-style: solid; }
  .assistant-bubble hr { border: 0; border-top: 1px solid #2a2d34; margin: 0.8em 0; }
  .assistant-bubble table { border-collapse: collapse; margin: 8px 0 }
  .assistant-bubble th, .assistant-bubble td { border: 1px solid #444; padding: 6px 10px }
  .assistant-bubble th { background: #2a2c30 }
  /* Blink-Caret bei Streaming */
  .assistant-bubble .caret {
    display: inline-block; width: 8px; height: 1em; vertical-align: text-bottom;
    background: #82b1ff; margin-left: 2px; animation: caret-blink 1s steps(2, start) infinite;
  }
  @keyframes caret-blink { to { visibility: hidden; } }
  /* Live-Status-Pill (vor der Antwort, zeigt was gerade passiert) */
  .status-pill {
    max-width: 75%; margin: 0 auto 10px 0; padding: 8px 14px;
    border-radius: 8px; background: #14171f; border: 1px solid #23262d;
    color: #9aa0aa; font-size: 12px; display: flex; align-items: center; gap: 10px;
  }
  .status-pill .spinner {
    width: 12px; height: 12px; border: 2px solid #2d2f36;
    border-top-color: #82b1ff; border-radius: 50%;
    animation: spin 0.8s linear infinite; flex-shrink: 0;
  }
  .status-pill .pill-text { color: #cfe1ff; font-weight: 500; }
  .status-pill .pill-sub { color: #7c818b; font-family: ui-monospace, monospace; font-size: 11px; }
  .status-pill.done { opacity: 0; transition: opacity 0.4s; pointer-events: none; height: 0; padding: 0; margin: 0; overflow: hidden; border: none; }
  @keyframes spin { to { transform: rotate(360deg); } }
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

  /* Dokumente-Tab */
  .doc-card-item {
    background: #16181d; border: 1px solid #23262d; border-radius: 6px;
    padding: 8px 10px; margin-bottom: 6px; font-size: 12px; cursor: pointer;
  }
  .doc-card-item:hover { border-color: #4669ff; }
  .doc-card-item .title { font-weight: 600; color: #e8eaed; }
  .doc-card-item .meta {
    color: #7c818b; font-size: 10px; font-family: ui-monospace, monospace;
    margin-top: 2px; display: flex; gap: 8px; flex-wrap: wrap;
  }
  .doc-card-item .meta .v { color: #82b1ff; }

  /* Document-Editor-Overlay */
  .overlay-card.doc-card { max-width: 1000px; width: 92%; max-height: 88vh; display: flex; flex-direction: column; }
  .overlay-card.doc-card .overlay-body {
    display: grid; grid-template-columns: 1fr 240px; gap: 12px; flex: 1; min-height: 0;
  }
  .overlay-card.doc-card .doc-editor-col { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
  #docVersions {
    display: flex; flex-direction: column; min-width: 0;
    border-left: 1px solid #23262d; padding-left: 12px;
  }
  #docVersions .head {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em;
    color: #7c818b; font-weight: 600; margin-bottom: 8px;
  }
  #docVersionsList { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
  #docVersionsList .ver-empty { color: #5a5d65; font-style: italic; font-size: 11px; padding: 4px 2px; }
  .ver-card {
    background: #16181d; border: 1px solid #23262d; border-radius: 5px;
    padding: 6px 8px; font-size: 11px; cursor: pointer;
  }
  .ver-card:hover { border-color: #4669ff; }
  .ver-card.active { border-color: #f0a050; background: #1d1812; }
  .ver-card .v { color: #82b1ff; font-weight: 600; font-family: ui-monospace, monospace; }
  .ver-card .author { color: #c5cad3; margin-left: 4px; }
  .ver-card .ts { color: #7c818b; font-size: 10px; font-family: ui-monospace, monospace; margin-top: 2px; }
  .doc-actions #docSave.restore { background: #d97a30; }
  .doc-actions #docSave.restore:hover { background: #e88a40; }
  #docTitle {
    width: 100%; background: #0e1014; color: #e8eaed; border: 1px solid #23262d;
    border-radius: 6px; padding: 8px 10px; font-size: 15px; font-weight: 600;
  }
  #docTitle:focus { border-color: #4669ff; outline: none; }
  #docContent {
    width: 100%; min-height: 360px; flex: 1;
    background: #0e1014; color: #e8eaed; border: 1px solid #23262d;
    border-radius: 6px 6px 0 0; padding: 10px 12px;
    font-family: ui-monospace, "SF Mono", monospace; font-size: 13px; line-height: 1.55;
    resize: vertical; tab-size: 2;
  }
  #docContent:focus { border-color: #4669ff; outline: none; }
  #docContent[readonly] { background: #16181d; color: #9aa0aa; }

  /* Editor-Toolbar */
  .doc-toolbar {
    display: flex; gap: 4px; flex-wrap: wrap;
    background: #14161a; border: 1px solid #23262d; border-bottom: none;
    border-radius: 6px 6px 0 0; padding: 4px 6px;
  }
  .doc-toolbar button {
    background: transparent; color: #9aa0aa; border: 1px solid transparent;
    border-radius: 4px; padding: 3px 8px; font-size: 12px; cursor: pointer;
    font-family: ui-monospace, monospace; height: auto; font-weight: 500;
  }
  .doc-toolbar button:hover { background: #1c1e23; color: #cfe1ff; }
  .doc-toolbar button.sep {
    background: none; cursor: default; padding: 0 2px; color: #2d2f36;
    pointer-events: none;
  }
  .doc-toolbar button kbd {
    font-family: inherit; font-size: 10px; color: #5a5d65; margin-left: 4px;
  }
  .doc-meta {
    display: flex; gap: 12px; padding: 4px 8px; font-size: 10px;
    color: #5a5d65; font-family: ui-monospace, monospace;
    border: 1px solid #23262d; border-top: none;
    border-radius: 0 0 6px 6px; background: #0e1014;
  }
  .doc-meta .grow { flex: 1; }
  .doc-meta .autosave-toggle { color: #82b1ff; cursor: pointer; user-select: none; }
  .doc-meta .autosave-toggle.on { color: #7ed99c; }
  .doc-meta .autosave-toggle:hover { text-decoration: underline; }
  /* Anpassung: Textarea-Border-Top oben durch toolbar abgedeckt */
  .doc-toolbar + #docContent { border-top: none; border-radius: 0; }
  .doc-actions {
    display: flex; gap: 8px; align-items: center;
    border-top: 1px solid #23262d; padding-top: 10px;
  }
  .doc-actions .doc-status { flex: 1; color: #7c818b; font-size: 11px; font-family: ui-monospace, monospace; }
  .doc-actions button { padding: 6px 14px; font-size: 12px; border-radius: 4px; border: none; cursor: pointer; }
  .doc-actions #docSave { background: #4669ff; color: #fff; font-weight: 500; }
  .doc-actions #docSave:hover { background: #5577ff; }
  .doc-actions #docSave:disabled { background: #2d2f36; color: #5a5d65; cursor: default; }
  .doc-actions #docDelete { background: #2d2f36; color: #f4a4a4; }
  .doc-actions #docDelete:hover { background: #3a2a2a; }

  /* Overlays (Entity-Detail + Error) — wie bisher */
  #overlay, #errOverlay, #docOverlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.55);
    display: none; align-items: center; justify-content: center; z-index: 100;
  }
  #overlay.open, #errOverlay.open, #docOverlay.open { display: flex; }
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

  /* Error-Overlay (Konsolen-Fehler) */
  .overlay-card.err-card { max-width: 760px; width: 92%; max-height: 80vh; }
  .overlay-card.err-card .overlay-head .title { color: #f08080; }
  .overlay-head .head-actions { display: flex; gap: 4px; align-items: center; }
  #errClearBtn {
    background: transparent; color: #9aa0aa; padding: 0 10px; height: 28px;
    font-weight: 500; font-size: 11px; cursor: pointer; border: 1px solid #2d2f36;
    border-radius: 4px; text-transform: uppercase; letter-spacing: 0.05em;
  }
  #errClearBtn:hover { color: #e8eaed; border-color: #3a3d46; }
  .err-empty { color: #7c818b; font-style: italic; padding: 12px 4px; text-align: center; }
  .err-entry {
    background: #1a1010; border: 1px solid #3a1818; border-radius: 6px;
    padding: 8px 10px; margin-bottom: 6px;
    font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px;
  }
  .err-entry .err-head { display: flex; justify-content: space-between; gap: 8px; }
  .err-entry .err-kind { color: #f08080; font-weight: 600; }
  .err-entry .err-ts { color: #7c818b; font-size: 11px; }
  .err-entry .err-msg { color: #f4a4a4; margin-top: 4px; white-space: pre-wrap; word-break: break-word; }
  .err-entry .err-where { color: #9aa0aa; font-size: 11px; margin-top: 3px; word-break: break-all; }
  .err-entry .err-stack {
    color: #8a94a8; font-size: 11px; margin-top: 4px;
    white-space: pre-wrap; word-break: break-word;
    max-height: 160px; overflow: auto;
    border-top: 1px dashed #2a1818; padding-top: 4px;
  }

  /* Diff-Overlay */
  #diffOverlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.55);
    display: none; align-items: center; justify-content: center; z-index: 110;
  }
  #diffOverlay.open { display: flex; }
  .overlay-card.diff-card { max-width: 980px; width: 92%; max-height: 86vh; display: flex; flex-direction: column; }
  .diff-body {
    flex: 1; overflow: auto; max-height: 70vh;
    background: #0e1014; border: 1px solid #23262d; border-radius: 6px;
    font-family: ui-monospace, "SF Mono", monospace; font-size: 12px; line-height: 1.5;
    padding: 4px 0;
  }
  .diff-title-row {
    padding: 6px 10px; margin-bottom: 4px;
    border-bottom: 1px solid #23262d; color: #9aa0aa; font-size: 12px;
  }
  .diff-title-row .lbl { color: #5a5d65; text-transform: uppercase; font-size: 10px; letter-spacing: 0.06em; margin-right: 6px; }
  .diff-title-row .ttl-from { color: #f08080; }
  .diff-title-row .ttl-to { color: #7ed99c; }
  .diff-title-row .arr { color: #5a5d65; margin: 0 6px; }
  .diff-line {
    display: flex; gap: 0; padding: 0 8px; white-space: pre-wrap; word-break: break-word;
  }
  .diff-line.equal { color: #9aa0aa; }
  .diff-line.delete { background: #2a1818; color: #f08080; }
  .diff-line.insert { background: #0e2018; color: #7ed99c; }
  .diff-ln {
    color: #5a5d65; font-family: ui-monospace, monospace; font-size: 11px;
    min-width: 32px; text-align: right; padding-right: 8px; user-select: none;
    flex-shrink: 0;
  }
  .diff-ln.gap { color: #3a3d46; }
  .diff-text { flex: 1; min-width: 0; }
  .diff-empty { padding: 20px; text-align: center; color: #7c818b; font-style: italic; }
  .ver-card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 4px; }
  .ver-diff-btn {
    background: transparent; color: #7c818b; border: 1px solid #2d2f36;
    border-radius: 3px; padding: 0 5px; font-size: 11px; cursor: pointer;
    font-family: ui-monospace, monospace; line-height: 16px; height: 18px;
  }
  .ver-diff-btn:hover { color: #82b1ff; border-color: #4669ff; }

  /* Action-Buttons (Doc-Overlay / Mappe-Menue) */
  .action-list { display: flex; flex-direction: column; gap: 4px; }
  .action-btn {
    background: #16181d; border: 1px solid #23262d; color: #cfe1ff;
    border-radius: 5px; padding: 6px 10px; font-size: 12px; cursor: pointer;
    text-align: left; display: flex; gap: 8px; align-items: center;
    font-weight: 500; line-height: 1.3;
  }
  .action-btn:hover { border-color: #4669ff; background: #1a1d28; }
  .action-btn.destructive { color: #f4a4a4; }
  .action-btn.destructive:hover { border-color: #b94343; background: #2a1818; }
  .action-btn .icon { font-size: 14px; flex-shrink: 0; }
  .action-btn .label { flex: 1; min-width: 0; }
  .action-btn .reason {
    color: #7c818b; font-size: 10px; font-style: italic; margin-top: 2px;
  }
  .action-btn .confirm-mark {
    color: #f0c674; font-size: 10px; flex-shrink: 0;
  }
  .action-empty { color: #5a5d65; font-style: italic; font-size: 11px; padding: 4px 2px; }
  .action-loading { color: #5a5d65; font-style: italic; font-size: 11px; padding: 4px 2px; }
  /* Mappe-Aktionen-Dropdown */
  .mappe-card-wrap { position: relative; }
  .mappe-actions-btn {
    position: absolute; top: 6px; right: 6px;
    background: transparent; border: none; color: #7c818b;
    cursor: pointer; padding: 0 6px; height: 22px; font-size: 14px;
    border-radius: 3px;
  }
  .mappe-actions-btn:hover { color: #82b1ff; background: #1a1d28; }
  .action-popup {
    position: absolute; top: 28px; right: 6px; z-index: 50;
    background: #14161a; border: 1px solid #2d2f36; border-radius: 6px;
    min-width: 200px; padding: 4px; box-shadow: 0 6px 22px rgba(0,0,0,0.5);
    display: none;
  }
  .action-popup.open { display: block; }
  .action-popup .action-btn { background: transparent; border: 1px solid transparent; }
  .action-popup .action-btn:hover { background: #1a1d28; border-color: #2d2f36; }

  /* Doc-Suche im Tab */
  .doc-search {
    width: 100%; padding: 6px 8px; margin-bottom: 8px;
    background: #0e1014; color: #e8eaed; border: 1px solid #23262d;
    border-radius: 6px; font-size: 12px; font-family: inherit;
  }
  .doc-search:focus { border-color: #4669ff; outline: none; }

  /* Chat-Kontext-Leiste (oberhalb des Input-Forms) */
  #chatContext {
    display: none; padding: 6px 18px; background: #14161a;
    border-top: 1px solid #25262b; font-size: 11px; color: #9aa0aa;
    align-items: center; gap: 8px; flex-wrap: wrap;
  }
  #chatContext.open { display: flex; }
  #chatContext .label { color: #cfe1ff; font-weight: 600; }
  #chatContext .label .cls { color: #7c818b; font-weight: 400; font-family: ui-monospace, monospace; font-size: 10px; margin-left: 4px; }
  #chatContext .pill {
    background: #1a1d28; border: 1px solid #2d2f36; border-radius: 14px;
    padding: 2px 10px; color: #82b1ff; cursor: pointer; font-size: 11px;
    font-weight: 500;
  }
  #chatContext .pill:hover { border-color: #4669ff; }
  #chatContext .pills { display: flex; gap: 4px; flex-wrap: wrap; flex: 1; }
  #chatContext .clear { cursor: pointer; color: #7c818b; padding: 0 4px; }
  #chatContext .clear:hover { color: #f4a4a4; }

  /* Action-Toast (fuer Tool-Call-Ergebnisse ohne Chat) */
  #actionToast {
    position: fixed; bottom: 20px; right: 20px; z-index: 200;
    background: #14161a; border: 1px solid #4669ff;
    border-radius: 8px; padding: 12px 16px; max-width: 480px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5); display: none;
    font-size: 12px; color: #e8eaed;
  }
  #actionToast.open { display: block; }
  #actionToast.err { border-color: #b94343; }
  #actionToast .title { font-weight: 600; margin-bottom: 4px; }
  #actionToast .body { color: #9aa0aa; font-family: ui-monospace, monospace; font-size: 11px; white-space: pre-wrap; max-height: 200px; overflow: auto; }
  #actionToast .close { float: right; cursor: pointer; color: #7c818b; }

  /* Error-Badge im Header */
  #errBadgeBtn {
    position: relative; padding: 0 10px; height: 30px; font-size: 14px;
    background: #2d2f36; color: #e8eaed; border: none; border-radius: 6px;
    cursor: pointer; display: none;
  }
  #errBadgeBtn.has-errors { display: inline-flex; align-items: center; gap: 6px; background: #3a1818; color: #f4a4a4; }
  #errBadgeBtn .count {
    background: #f08080; color: #1a0a0a; font-weight: 700;
    font-size: 11px; padding: 1px 6px; border-radius: 10px;
    font-family: ui-monospace, monospace;
  }

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
    <button type="button" id="errBadgeBtn" title="Konsolen-Fehler anzeigen">⚠ <span class="count" id="errBadgeCount">0</span></button>
    <button type="button" class="icon" id="debugToggle" title="Debug-Panel umschalten">🐞</button>
  </span>
</header>
<div id="layout">
  <aside id="sidebar">
    <div class="tabbar">
      <button class="tabbtn active" data-tab="sessions">Sessions</button>
      <button class="tabbtn" data-tab="mappe">Mappe</button>
      <button class="tabbtn" data-tab="dokumente">Dokumente</button>
    </div>
    <div class="tabbody" id="tab-sessions">
      <button class="new-chat-btn" id="newChatBtn">+ Neuer Chat</button>
      <div id="sessionsList"></div>
    </div>
    <div class="tabbody hidden" id="tab-mappe">
      <div class="mappe-empty" id="mappeEmpty">Keine aktive Session.</div>
      <div id="mappeContent" class="hidden">
        <div class="section-h">Dokumente</div>
        <div id="mappeDocs"></div>
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
    <div class="tabbody hidden" id="tab-dokumente">
      <button class="new-chat-btn" id="newDocBtn">+ Neues Dokument</button>
      <input type="search" class="doc-search" id="docSearch" placeholder="Titel oder Inhalt suchen…" />
      <div id="docList"></div>
      <div class="mappe-empty" id="docEmpty">Noch keine Dokumente.</div>
    </div>
  </aside>
  <div id="chat">
    <div id="log"></div>
    <div id="chatContext">
      <span class="label" id="chatContextLabel"></span>
      <div id="chatContextActions" class="pills"></div>
      <span class="clear" id="chatContextClear" title="Kontext entfernen">✕</span>
    </div>
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
<div id="docOverlay" role="dialog" aria-modal="true">
  <div class="overlay-card doc-card">
    <div class="overlay-head">
      <div><span class="title">Dokument</span><span class="sub" id="docSub">—</span></div>
      <button type="button" id="docOverlayClose" title="Schließen">✕</button>
    </div>
    <div class="overlay-body">
      <div class="doc-editor-col">
        <input id="docTitle" type="text" placeholder="Titel…" maxlength="255" />
        <div class="doc-toolbar" id="docToolbar">
          <button type="button" data-md="h1" title="Heading 1">H1</button>
          <button type="button" data-md="h2" title="Heading 2">H2</button>
          <button type="button" data-md="h3" title="Heading 3">H3</button>
          <button class="sep">|</button>
          <button type="button" data-md="bold" title="Fett (Ctrl/Cmd+B)"><b>B</b></button>
          <button type="button" data-md="italic" title="Kursiv (Ctrl/Cmd+I)"><i>I</i></button>
          <button type="button" data-md="code" title="Inline-Code"><code>‹›</code></button>
          <button class="sep">|</button>
          <button type="button" data-md="ul" title="Aufzählung">• Liste</button>
          <button type="button" data-md="ol" title="Nummerierte Liste">1. Liste</button>
          <button type="button" data-md="quote" title="Zitat">❝</button>
          <button class="sep">|</button>
          <button type="button" data-md="link" title="Link (Ctrl/Cmd+K)">🔗</button>
          <button type="button" data-md="codeblock" title="Code-Block">```</button>
        </div>
        <textarea id="docContent" placeholder="Markdown… (Tab indent · Ctrl/Cmd+S speichern · Ctrl/Cmd+B/I/K)" spellcheck="false"></textarea>
        <div class="doc-meta">
          <span id="docCharCount">0 Zeichen</span>
          <span id="docLineCount">1 Zeile</span>
          <span class="grow"></span>
          <span class="autosave-toggle" id="docAutosaveToggle" title="Auto-Save alle 3s nach letzter Änderung">Auto-Save: aus</span>
        </div>
        <div class="doc-actions">
          <span class="doc-status" id="docStatus">—</span>
          <button type="button" id="docDelete" class="danger">Löschen</button>
          <button type="button" id="docSave">Speichern</button>
        </div>
      </div>
      <aside id="docVersions">
        <div class="head">Versionen</div>
        <div id="docVersionsList"><div class="ver-empty">—</div></div>
        <div class="head" style="margin-top:14px">Aktionen</div>
        <div id="docActions" class="action-list">
          <div class="action-empty">—</div>
        </div>
      </aside>
    </div>
  </div>
</div>
<div id="actionToast" role="status">
  <span class="close" id="actionToastClose">✕</span>
  <div class="title" id="actionToastTitle">Ergebnis</div>
  <div class="body" id="actionToastBody"></div>
</div>
<div id="errOverlay" role="dialog" aria-modal="true">
  <div class="overlay-card err-card">
    <div class="overlay-head">
      <div><span class="title">Konsolen-Fehler</span><span class="sub" id="errSub">0</span></div>
      <div class="head-actions">
        <button type="button" id="errClearBtn" title="Liste leeren">Leeren</button>
        <button type="button" id="errOverlayClose" title="Schließen">✕</button>
      </div>
    </div>
    <div class="overlay-body" id="errOverlayBody"><div class="err-empty">Keine Fehler.</div></div>
  </div>
</div>
<div id="diffOverlay" role="dialog" aria-modal="true">
  <div class="overlay-card diff-card">
    <div class="overlay-head">
      <div><span class="title" id="diffTitle">Diff</span><span class="sub" id="diffSub">—</span></div>
      <button type="button" id="diffOverlayClose" title="Schließen">✕</button>
    </div>
    <div class="diff-body" id="diffBody"><div class="diff-empty">—</div></div>
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

  // ---------- Error-Overlay: Konsolen-Fehler einsammeln & anzeigen ----------
  // Hookt console.error, window.error, unhandledrejection. Jeder Fehler erscheint
  // im Overlay und im Header-Badge (Counter). Originales console.error bleibt erhalten.
  const errOverlay = document.getElementById('errOverlay');
  const errOverlayBody = document.getElementById('errOverlayBody');
  const errSub = document.getElementById('errSub');
  const errBadgeBtn = document.getElementById('errBadgeBtn');
  const errBadgeCount = document.getElementById('errBadgeCount');
  let errCount = 0;
  let errReporting = false;  // Re-Entry-Guard

  function openErrOverlay() { errOverlay.classList.add('open'); }
  function closeErrOverlay() { errOverlay.classList.remove('open'); }
  function updateErrBadge() {
    errBadgeCount.textContent = String(errCount);
    errBadgeBtn.classList.toggle('has-errors', errCount > 0);
    errSub.textContent = String(errCount);
  }
  function clearErrors() {
    errCount = 0;
    errOverlayBody.innerHTML = '<div class="err-empty">Keine Fehler.</div>';
    updateErrBadge();
  }
  function stringifyArg(a) {
    if (a instanceof Error) return a.message;
    if (a === null) return 'null';
    if (a === undefined) return 'undefined';
    if (typeof a === 'object') {
      try { return JSON.stringify(a); } catch (_) { return String(a); }
    }
    return String(a);
  }
  function reportError(kind, parts, opts) {
    if (errReporting) return;  // verhindert Endlosschleifen
    errReporting = true;
    try {
      opts = opts || {};
      if (errCount === 0) errOverlayBody.innerHTML = '';
      errCount += 1;
      updateErrBadge();
      const entry = el('div', 'err-entry');
      const head = el('div', 'err-head');
      head.appendChild(el('span', 'err-kind', kind));
      head.appendChild(el('span', 'err-ts', new Date().toLocaleTimeString([], { hour12: false })));
      entry.appendChild(head);
      const msgText = (parts || []).map(stringifyArg).join(' ');
      if (msgText) {
        const msg = el('div', 'err-msg');
        msg.textContent = msgText;
        entry.appendChild(msg);
      }
      if (opts.where) entry.appendChild(el('div', 'err-where', opts.where));
      if (opts.stack) {
        const st = el('div', 'err-stack');
        st.textContent = opts.stack;
        entry.appendChild(st);
      }
      errOverlayBody.appendChild(entry);
      errOverlayBody.scrollTop = errOverlayBody.scrollHeight;
      openErrOverlay();
    } catch (_) { /* schluck — kein erneutes Reporting */ }
    finally { errReporting = false; }
  }

  const _origConsoleError = console.error.bind(console);
  console.error = function(...args) {
    _origConsoleError(...args);
    const errArg = args.find(a => a instanceof Error);
    reportError('console.error', args, { stack: errArg ? errArg.stack : null });
  };
  window.addEventListener('error', (e) => {
    const where = e.filename ? `${e.filename}:${e.lineno || 0}:${e.colno || 0}` : '';
    const stack = e.error && e.error.stack ? e.error.stack : null;
    reportError('window.error', [e.message || 'Unbekannter Fehler'], { where, stack });
  });
  window.addEventListener('unhandledrejection', (e) => {
    const r = e.reason;
    const msg = r instanceof Error ? r.message : stringifyArg(r);
    const stack = r && r.stack ? r.stack : null;
    reportError('unhandledrejection', [msg], { stack });
  });

  errBadgeBtn.addEventListener('click', openErrOverlay);
  document.getElementById('errOverlayClose').addEventListener('click', closeErrOverlay);
  document.getElementById('errClearBtn').addEventListener('click', clearErrors);
  errOverlay.addEventListener('click', (e) => { if (e.target === errOverlay) closeErrOverlay(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && errOverlay.classList.contains('open')) closeErrOverlay();
  });
  updateErrBadge();

  // ---------- Markdown-Rendering (marked + DOMPurify aus CDN) ----------
  if (window.marked && window.marked.setOptions) {
    window.marked.setOptions({ breaks: true, gfm: true });
  }
  function renderMarkdown(src) {
    const text = String(src == null ? '' : src);
    // Falls Backend bereits HTML (z.B. Entity-Links) liefert: nicht doppelt parsen,
    // sondern via DOMPurify durchreichen. Heuristik: enthält '<a class="entity-link"'.
    const looksLikeHtml = /<a\\s+class="entity-link"/i.test(text);
    let html;
    try {
      if (looksLikeHtml) {
        html = text;
      } else if (window.marked) {
        html = window.marked.parse(text);
      } else {
        html = escapeHtml(text).replace(/\\n/g, '<br>');
      }
    } catch (_err) {
      html = escapeHtml(text).replace(/\\n/g, '<br>');
    }
    if (window.DOMPurify) {
      html = window.DOMPurify.sanitize(html, {
        ADD_ATTR: ['data-entity', 'data-id', 'data-bound', 'target'],
      });
    }
    return html;
  }

  function addMsg(role, content) {
    const div = el('div', 'msg ' + role);
    div.appendChild(el('div', 'role', role));
    const body = document.createElement('div');
    if (role === 'assistant') {
      body.className = 'assistant-bubble';
      body.innerHTML = renderMarkdown(content);
      wireEntityLinks(body);
    } else {
      body.textContent = content;
    }
    div.appendChild(body);
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  // ---------- Live-Status-Pill + Streaming-Bubble ----------
  // Wird beim Senden einer Nachricht erzeugt. Pill zeigt was gerade passiert
  // (Intent klassifizieren, Tool laufen, Antwort schreiben). Die Bubble wird
  // per llm_delta-Events live mit dem Antwort-Text gefuellt.
  function createPendingExchange() {
    const pill = el('div', 'status-pill');
    pill.appendChild(el('span', 'spinner'));
    const txt = el('span', 'pill-text', 'Denke nach…');
    pill.appendChild(txt);
    const sub = el('span', 'pill-sub', '');
    pill.appendChild(sub);
    log.appendChild(pill);

    const bubble = el('div', 'msg assistant');
    bubble.style.display = 'none';
    bubble.appendChild(el('div', 'role', 'assistant'));
    const body = document.createElement('div');
    body.className = 'assistant-bubble';
    bubble.appendChild(body);
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;

    let raw = '';
    let renderQueued = false;

    function showBubbleIfNeeded() {
      if (bubble.style.display === 'none') {
        bubble.style.display = '';
      }
    }
    function scheduleRender() {
      if (renderQueued) return;
      renderQueued = true;
      requestAnimationFrame(() => {
        renderQueued = false;
        body.innerHTML = renderMarkdown(raw) + '<span class="caret"></span>';
        log.scrollTop = log.scrollHeight;
      });
    }
    function appendDelta(delta) {
      if (!delta) return;
      raw += delta;
      showBubbleIfNeeded();
      scheduleRender();
    }
    function resetStream() {
      // Wird zwischen mehreren Tool-Runden aufgerufen, damit jede Runde
      // mit einer leeren Bubble streamt (die finale Antwort kommt am Ende
      // via finalize() ohnehin canonical aus dem done-Event).
      raw = '';
      body.innerHTML = '';
      bubble.style.display = 'none';
    }
    function setStatus(text, sub2) {
      txt.textContent = text;
      sub.textContent = sub2 || '';
    }
    function dismissPill() {
      pill.classList.add('done');
      setTimeout(() => { try { pill.remove(); } catch (_e) {} }, 500);
    }
    function finalize(finalText, opts) {
      opts = opts || {};
      dismissPill();
      if (opts.error) {
        try { bubble.remove(); } catch (_e) {}
        addMsg('error', 'Fehler: ' + (finalText || 'unbekannt'));
        return;
      }
      const canonical = (finalText != null ? finalText : raw) || '';
      if (!canonical) {
        try { bubble.remove(); } catch (_e) {}
        return;
      }
      showBubbleIfNeeded();
      body.innerHTML = renderMarkdown(canonical);
      wireEntityLinks(body);
      log.scrollTop = log.scrollHeight;
    }
    return { appendDelta, resetStream, setStatus, finalize };
  }

  const TOOL_LABELS = {
    sales_support: 'Sales-Support',
    contact_get: 'Kontakt laden',
    contact_upsert: 'Kontakt speichern',
    account_get: 'Account laden',
    account_upsert: 'Account speichern',
    lead_get: 'Lead laden',
    lead_create: 'Lead anlegen',
    lead_convert: 'Lead konvertieren',
    deal_get: 'Deal laden',
    deal_create: 'Deal anlegen',
    deal_advance_stage: 'Deal-Stage weiterstufen',
  };
  function labelTool(name) {
    return TOOL_LABELS[name] || name;
  }
  function statusForEvent(ev) {
    const d = ev.data || {};
    switch (ev.event_type) {
      case 'trace_started':    return { text: 'Starte…' };
      case 'intent_classified': return { text: 'Plane Antwort…', sub: 'Intent: ' + (d.intent || '?') };
      case 'mcp_connected':    return { text: 'Verbunden mit Werkzeugen', sub: (d.tool_names || []).length + ' Tools' };
      case 'llm_request':      return { text: d.has_tools ? 'Denke nach (Runde ' + (d.round || 1) + ')…' : 'Schreibt Antwort…' };
      case 'llm_response':     return { text: d.has_tool_calls ? 'Plant Tool-Einsatz…' : 'Antwort fertig…' };
      case 'tool_call_started': return { text: 'Nutze ' + labelTool(d.tool_name) + '…', sub: d.tool_name };
      case 'tool_call_result': return { text: 'Tool-Antwort verarbeiten…', sub: labelTool(d.tool_name) + ' · ' + (d.duration_ms || 0) + 'ms' };
      case 'error':            return { text: 'Fehler', sub: d.message || '' };
      default: return null;
    }
  }

  // ---------- Tabs ----------
  document.querySelectorAll('.tabbtn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tabbtn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.tabbody').forEach(b => b.classList.add('hidden'));
      document.getElementById('tab-' + btn.dataset.tab).classList.remove('hidden');
      if (btn.dataset.tab === 'mappe') refreshMappe();
      if (btn.dataset.tab === 'dokumente') refreshDocs();
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
      const delBtn = el('button', 'danger', 'Archivieren');
      delBtn.title = 'Chat ins Archiv verschieben (Soft-Delete)';
      delBtn.addEventListener('click', (e) => { e.stopPropagation(); archiveSession(c.id, c.title || ('Chat #' + c.id)); });
      actions.appendChild(delBtn);
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

  // ---------- Deep-Link: ?chat=<id> in der URL ----------
  function chatIdFromUrl() {
    const m = new URLSearchParams(window.location.search).get('chat');
    if (!m) return null;
    const n = parseInt(m, 10);
    return Number.isFinite(n) && n > 0 ? n : null;
  }
  function syncUrlToChat(chatId, mode) {
    // mode: 'push' (neuer Verlauf-Eintrag) oder 'replace' (kein Back-History-Spam)
    const url = new URL(window.location.href);
    if (chatId) url.searchParams.set('chat', String(chatId));
    else url.searchParams.delete('chat');
    if (url.toString() === window.location.href) return;  // kein Re-Push fuer gleichen Chat
    const fn = mode === 'replace' ? 'replaceState' : 'pushState';
    history[fn]({ chatId: chatId || null }, '', url.toString());
  }

  async function loadChat(chatId, opts) {
    opts = opts || {};
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
    if (opts.updateUrl !== false) syncUrlToChat(chatId, opts.urlMode || 'push');
  }

  // Back/Forward: zwischen geteilten/aufgerufenen Chats navigieren
  window.addEventListener('popstate', () => {
    const id = chatIdFromUrl();
    if (id && id !== currentChatId) loadChat(id, { updateUrl: false });
  });

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

  async function archiveSession(chatId, title) {
    if (!confirm('Chat „' + title + '" ins Archiv verschieben?')) return;
    try {
      const resp = await fetch(API('/chats/' + chatId), { method: 'DELETE' });
      if (!resp.ok) {
        addMsg('error', 'Archivieren fehlgeschlagen: HTTP ' + resp.status);
        return;
      }
      if (chatId === currentChatId) {
        currentChatId = null;
        log.innerHTML = '';
        syncUrlToChat(null, 'replace');
      }
      await refreshSessions();
    } catch (err) { console.error('archive failed', err); }
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
      renderMappeDocs(data.documents || []);
      renderFiles(data.files || []);
      renderCrm(data.crm_entities || []);
      renderTnc(data.tasks_notes_comments || {});
      renderToolCalls(data.tool_calls || []);
    } catch (err) {
      console.error('mappe failed', err);
    }
  }

  // Mappe-Aktions-Popup: kleiner "..."-Button + Dropdown mit Top-3 Aktionen.
  // ctx = {cls, id}. Wir laden die Aktionen lazy on-open.
  function attachMappeActions(card, ctx) {
    const wrap = el('div', 'mappe-card-wrap');
    wrap.appendChild(card);
    const btn = document.createElement('button');
    btn.className = 'mappe-actions-btn';
    btn.type = 'button';
    btn.title = 'Aktionen';
    btn.innerHTML = '⋯';
    const popup = el('div', 'action-popup');
    popup.innerHTML = '<div class="action-loading">Lade…</div>';
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      // andere Popups schließen
      for (const p of document.querySelectorAll('.action-popup.open')) {
        if (p !== popup) p.classList.remove('open');
      }
      const willOpen = !popup.classList.contains('open');
      popup.classList.toggle('open', willOpen);
      if (willOpen && popup.dataset.loaded !== '1') {
        await loadActions(popup, { cls: ctx.cls, id: ctx.id });
        popup.dataset.loaded = '1';
      }
    });
    wrap.appendChild(btn);
    wrap.appendChild(popup);
    return wrap;
  }

  // Klick außerhalb schließt alle Popups
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.action-popup') && !e.target.closest('.mappe-actions-btn')) {
      for (const p of document.querySelectorAll('.action-popup.open')) p.classList.remove('open');
    }
  });

  function renderMappeDocs(docs) {
    const c = document.getElementById('mappeDocs');
    c.innerHTML = '';
    if (!docs.length) { c.innerHTML = '<div class="mappe-empty">keine Dokumente</div>'; return; }
    docs.forEach(d => {
      const card = el('div', 'artifact-card clickable');
      card.dataset.docId = String(d.id);
      const rel = el('span', 'rel', d.relation || '');
      card.appendChild(rel);
      card.appendChild(el('div', 'title', d.title || ('#' + d.id)));
      card.appendChild(el('div', 'meta', `v${d.version} · ${escapeHtml(d.author_display_name || '')} · ${fmtDate(d.updated_at)}`));
      card.addEventListener('click', () => openDoc(d.id));
      c.appendChild(attachMappeActions(card, { cls: 'core.document', id: d.id }));
    });
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
      c.appendChild(attachMappeActions(card, { cls: e.artifact_cls, id: e.artifact_id }));
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
    const pending = createPendingExchange();
    const stats = { events: 0, llm_calls: 0, tool_calls: 0, tokens_in: 0, tokens_out: 0, duration_ms: null };
    try {
      const resp = await fetch(API('/chats/' + currentChatId + '/messages'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg }),
      });
      if (!resp.ok || !resp.body) {
        pending.finalize('HTTP ' + resp.status, { error: true });
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
            const ev = sse.data;
            const d = ev.data || {};
            // Streaming-Delta direkt in die Bubble pumpen
            if (ev.event_type === 'llm_delta') {
              pending.appendDelta(d.content_delta || '');
              // Status mitziehen, aber nur einmal pro Stream
              if (!pending._streamingStatus) {
                pending._streamingStatus = true;
                pending.setStatus('Schreibt Antwort…', 'Runde ' + (d.round || 1));
              }
              // Volatile Events nicht in Debug-Stats zaehlen, aber im Debug-Panel zeigen ist optional
              continue;
            }
            stats.events += 1;
            if (ev.event_type === 'llm_response') stats.llm_calls += 1;
            if (ev.event_type === 'tool_call_started') stats.tool_calls += 1;
            if (d.prompt_tokens) stats.tokens_in += d.prompt_tokens;
            if (d.completion_tokens) stats.tokens_out += d.completion_tokens;
            const s = statusForEvent(ev);
            if (s) pending.setStatus(s.text, s.sub);
            // Neue Runde → Bubble leeren, damit nur die finale Antwort gestreamt aussieht
            if (ev.event_type === 'llm_request') {
              pending._streamingStatus = false;
              pending.resetStream();
            }
            dbgAppend(ev);
            dbgUpdateStats(stats);
          } else if (sse.name === 'done') {
            final = sse.data;
          }
        }
      }
      if (!final) {
        pending.finalize('Stream ohne done-Event', { error: true });
        return;
      }
      stats.duration_ms = final.duration_ms;
      dbgUpdateStats(stats);
      if (final.status === 'error') {
        pending.finalize(final.error_message || 'unbekannt', { error: true });
      } else {
        pending.finalize(final.response);
      }
      await refreshSessions();
      if (!document.getElementById('tab-mappe').classList.contains('hidden')) await refreshMappe();
    } catch (err) {
      pending.finalize('Netzwerkfehler: ' + err, { error: true });
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

  // ---------- Dokumente ----------
  let currentDocId = null;
  let docDirty = false;
  let viewingVersionId = null;   // wenn != null: schreibgeschuetzte Ansicht einer alten Version
  const docOverlay = document.getElementById('docOverlay');
  const docTitle = document.getElementById('docTitle');
  const docContent = document.getElementById('docContent');
  const docStatus = document.getElementById('docStatus');
  const docSaveBtn = document.getElementById('docSave');
  const docDeleteBtn = document.getElementById('docDelete');
  const docSub = document.getElementById('docSub');
  const docList = document.getElementById('docList');
  const docEmpty = document.getElementById('docEmpty');
  const docVersionsList = document.getElementById('docVersionsList');

  function setDocStatus(text, kind) {
    docStatus.textContent = text;
    docStatus.style.color = kind === 'err' ? '#f08080' : kind === 'ok' ? '#7ed99c' : '#7c818b';
  }
  function setDocDirty(dirty) {
    docDirty = dirty;
    docSaveBtn.disabled = !dirty;
    if (dirty) setDocStatus('Ungespeicherte Änderungen', '');
  }
  function openDocOverlay() { docOverlay.classList.add('open'); }
  function closeDocOverlay() {
    docOverlay.classList.remove('open');
    currentDocId = null;
    docDirty = false;
    exitVersionView();
    clearDocVersions();
  }

  function clearDocVersions() {
    docVersionsList.innerHTML = '<div class="ver-empty">—</div>';
  }

  function setSaveButtonMode(mode) {
    // mode: 'save' (Standard) oder 'restore' (orange Akzent)
    if (mode === 'restore') {
      docSaveBtn.textContent = 'Wiederherstellen';
      docSaveBtn.classList.add('restore');
    } else {
      docSaveBtn.textContent = 'Speichern';
      docSaveBtn.classList.remove('restore');
    }
  }

  function exitVersionView() {
    viewingVersionId = null;
    docTitle.readOnly = false;
    docContent.readOnly = false;
    setSaveButtonMode('save');
    // active-Markierung in der Versions-Liste entfernen
    for (const c of docVersionsList.querySelectorAll('.ver-card.active')) {
      c.classList.remove('active');
    }
  }

  async function refreshDocVersions() {
    if (currentDocId == null) { clearDocVersions(); return; }
    try {
      const r = await fetch(API('/documents/' + currentDocId + '/versions?limit=200'));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      const versions = data.versions || [];
      docVersionsList.innerHTML = '';
      if (versions.length === 0) {
        docVersionsList.innerHTML = '<div class="ver-empty">Noch keine alten Versionen</div>';
        return;
      }
      for (const v of versions) {
        const card = el('div', 'ver-card');
        card.dataset.versionId = v.id;
        card.innerHTML = `
          <div class="ver-card-head">
            <div><span class="v">v${v.version}</span><span class="author">${escapeHtml(v.author_display_name || '')}</span></div>
            <button type="button" class="ver-diff-btn" title="Diff gegen aktuell">&Delta;</button>
          </div>
          <div class="ts">${fmtDate(v.created_at)}</div>
        `;
        card.addEventListener('click', (ev) => {
          if (ev.target.classList.contains('ver-diff-btn')) return;
          viewDocVersion(v.id);
        });
        const diffBtn = card.querySelector('.ver-diff-btn');
        diffBtn.addEventListener('click', (ev) => {
          ev.stopPropagation();
          openDiff(v.id);
        });
        docVersionsList.appendChild(card);
      }
    } catch (err) {
      docVersionsList.innerHTML = '<div class="ver-empty">Laden fehlgeschlagen: ' + escapeHtml(String(err)) + '</div>';
    }
  }

  async function viewDocVersion(versionId) {
    if (currentDocId == null) return;
    if (docDirty && !confirm('Ungespeicherte Änderungen verwerfen?')) return;
    try {
      const r = await fetch(API('/documents/' + currentDocId + '/versions/' + versionId));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const v = await r.json();
      docTitle.value = v.title || '';
      docContent.value = v.content || '';
      docTitle.readOnly = true;
      docContent.readOnly = true;
      viewingVersionId = versionId;
      docDirty = false;
      docSaveBtn.disabled = false;
      setSaveButtonMode('restore');
      setDocStatus(`Vorschau v${v.version} · ${fmtDate(v.created_at)}`, '');
      for (const c of docVersionsList.querySelectorAll('.ver-card')) {
        c.classList.toggle('active', c.dataset.versionId === String(versionId));
      }
    } catch (err) {
      alert('Version laden fehlgeschlagen: ' + err);
    }
  }

  async function restoreDocVersion() {
    if (currentDocId == null || viewingVersionId == null) return;
    if (!confirm('Diese Version wiederherstellen? Der aktuelle Stand wird vorher als Snapshot gesichert.')) return;
    docSaveBtn.disabled = true;
    setDocStatus('Stelle wieder her…', '');
    try {
      const r = await fetch(
        API('/documents/' + currentDocId + '/versions/' + viewingVersionId + '/restore'),
        { method: 'POST' },
      );
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const doc = await r.json();
      currentDocId = doc.id;
      docTitle.value = doc.title || '';
      docContent.value = doc.content || '';
      docSub.textContent = `#${doc.id} · v${doc.version} · ${fmtDate(doc.updated_at)}`;
      exitVersionView();
      setDocDirty(false);
      setDocStatus('Wiederhergestellt', 'ok');
      await refreshDocs();
      await refreshDocVersions();
    } catch (err) {
      setDocStatus('Fehler: ' + err, 'err');
      docSaveBtn.disabled = false;
    }
  }

  async function refreshDocs() {
    try {
      const r = await fetch(API('/documents?limit=200'));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      const docs = data.documents || [];
      docList.innerHTML = '';
      if (docs.length === 0) {
        docEmpty.style.display = '';
        return;
      }
      docEmpty.style.display = 'none';
      for (const d of docs) {
        const card = el('div', 'doc-card-item');
        card.innerHTML = `
          <div class="title">${escapeHtml(d.title)}</div>
          <div class="meta">
            <span class="v">v${d.version}</span>
            <span>${escapeHtml(d.author_display_name || '')}</span>
            <span>${fmtDate(d.updated_at)}</span>
          </div>
        `;
        card.addEventListener('click', () => openDoc(d.id));
        docList.appendChild(card);
      }
    } catch (err) {
      docList.innerHTML = '';
      docEmpty.textContent = 'Laden fehlgeschlagen: ' + err;
      docEmpty.style.display = '';
    }
  }

  async function openDoc(id) {
    try {
      const r = await fetch(API('/documents/' + id));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const doc = await r.json();
      currentDocId = doc.id;
      docTitle.value = doc.title || '';
      docContent.value = doc.content || '';
      docSub.textContent = `#${doc.id} · v${doc.version} · ${fmtDate(doc.updated_at)}`;
      exitVersionView();
      setDocDirty(false);
      setDocStatus('Geladen', '');
      openDocOverlay();
      docTitle.focus();
      refreshDocVersions();
    } catch (err) {
      alert('Dokument laden fehlgeschlagen: ' + err);
    }
  }

  async function createDoc() {
    currentDocId = null;
    docTitle.value = '';
    docContent.value = '';
    docSub.textContent = 'Neu';
    exitVersionView();
    clearDocVersions();
    setDocStatus('Noch nicht gespeichert', '');
    docSaveBtn.disabled = false;
    docDirty = true;
    openDocOverlay();
    docTitle.focus();
  }

  async function saveDoc() {
    // Wenn eine alte Version gerade angezeigt wird, ist "Speichern" = Wiederherstellen
    if (viewingVersionId != null) {
      await restoreDocVersion();
      return;
    }
    const title = docTitle.value.trim();
    const content = docContent.value;
    docSaveBtn.disabled = true;
    setDocStatus('Speichere…', '');
    try {
      let url, method, body;
      if (currentDocId == null) {
        url = API('/documents');
        method = 'POST';
        body = { title, content };
      } else {
        url = API('/documents/' + currentDocId);
        method = 'PUT';
        body = { title, content };
      }
      const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const doc = await r.json();
      currentDocId = doc.id;
      docSub.textContent = `#${doc.id} · v${doc.version} · ${fmtDate(doc.updated_at)}`;
      setDocDirty(false);
      setDocStatus('Gespeichert', 'ok');
      await refreshDocs();
      await refreshDocVersions();
    } catch (err) {
      setDocStatus('Fehler: ' + err, 'err');
      docSaveBtn.disabled = false;
    }
  }

  async function deleteDoc() {
    if (currentDocId == null) { closeDocOverlay(); return; }
    if (!confirm('Dokument wirklich löschen?')) return;
    try {
      const r = await fetch(API('/documents/' + currentDocId), { method: 'DELETE' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      closeDocOverlay();
      await refreshDocs();
    } catch (err) {
      setDocStatus('Löschen fehlgeschlagen: ' + err, 'err');
    }
  }

  document.getElementById('newDocBtn').addEventListener('click', createDoc);
  docSaveBtn.addEventListener('click', saveDoc);
  docDeleteBtn.addEventListener('click', deleteDoc);
  document.getElementById('docOverlayClose').addEventListener('click', () => {
    if (docDirty && !confirm('Ungespeicherte Änderungen verwerfen?')) return;
    closeDocOverlay();
  });
  docOverlay.addEventListener('click', (e) => {
    if (e.target === docOverlay) {
      if (docDirty && !confirm('Ungespeicherte Änderungen verwerfen?')) return;
      closeDocOverlay();
    }
  });

  // ---------- Diff-Overlay ----------
  const diffOverlay = document.getElementById('diffOverlay');
  const diffTitle = document.getElementById('diffTitle');
  const diffSub = document.getElementById('diffSub');
  const diffBody = document.getElementById('diffBody');

  function closeDiffOverlay() {
    diffOverlay.classList.remove('open');
    diffBody.innerHTML = '<div class="diff-empty">—</div>';
  }
  document.getElementById('diffOverlayClose').addEventListener('click', closeDiffOverlay);
  diffOverlay.addEventListener('click', (e) => {
    if (e.target === diffOverlay) closeDiffOverlay();
  });

  function renderDiffLines(contentDiff) {
    // Inline-Diff: pro Opcode Zeilen rendern mit from/to-Linenumbers
    const out = [];
    for (const op of contentDiff) {
      const oldLines = op.old_text === '' && op.old_start === op.old_end ? [] : op.old_text.split('\\n');
      const newLines = op.new_text === '' && op.new_start === op.new_end ? [] : op.new_text.split('\\n');
      if (op.kind === 'equal') {
        for (let k = 0; k < oldLines.length; k++) {
          const oi = op.old_start + k + 1;
          const ni = op.new_start + k + 1;
          out.push(`<div class="diff-line equal"><span class="diff-ln">${oi}</span><span class="diff-ln">${ni}</span><span class="diff-text">${escapeHtml(oldLines[k] || '')}</span></div>`);
        }
      } else if (op.kind === 'delete') {
        for (let k = 0; k < oldLines.length; k++) {
          const oi = op.old_start + k + 1;
          out.push(`<div class="diff-line delete"><span class="diff-ln">${oi}</span><span class="diff-ln gap">·</span><span class="diff-text">- ${escapeHtml(oldLines[k] || '')}</span></div>`);
        }
      } else if (op.kind === 'insert') {
        for (let k = 0; k < newLines.length; k++) {
          const ni = op.new_start + k + 1;
          out.push(`<div class="diff-line insert"><span class="diff-ln gap">·</span><span class="diff-ln">${ni}</span><span class="diff-text">+ ${escapeHtml(newLines[k] || '')}</span></div>`);
        }
      } else if (op.kind === 'replace') {
        // delete-Block, dann insert-Block
        for (let k = 0; k < oldLines.length; k++) {
          const oi = op.old_start + k + 1;
          out.push(`<div class="diff-line delete"><span class="diff-ln">${oi}</span><span class="diff-ln gap">·</span><span class="diff-text">- ${escapeHtml(oldLines[k] || '')}</span></div>`);
        }
        for (let k = 0; k < newLines.length; k++) {
          const ni = op.new_start + k + 1;
          out.push(`<div class="diff-line insert"><span class="diff-ln gap">·</span><span class="diff-ln">${ni}</span><span class="diff-text">+ ${escapeHtml(newLines[k] || '')}</span></div>`);
        }
      }
    }
    return out.join('');
  }

  async function openDiff(versionId, against) {
    if (currentDocId == null) return;
    against = against || 'current';
    diffTitle.textContent = 'Diff';
    diffSub.textContent = 'lädt…';
    diffBody.innerHTML = '<div class="diff-empty">lädt…</div>';
    diffOverlay.classList.add('open');
    try {
      const url = API('/documents/' + currentDocId + '/versions/' + versionId + '/diff?against=' + encodeURIComponent(against));
      const r = await fetch(url);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      const fromV = data.from || {};
      const toV = data.to || {};
      diffTitle.textContent = `Diff: v${fromV.version} → ${toV.label === 'aktuell' ? 'aktuell' : 'v' + toV.version}`;
      diffSub.textContent = `${fromV.label} → ${toV.label}`;

      let html = '';
      // Titel-Diff oben anzeigen, wenn unterschiedlich
      const td = (data.title_diff || [])[0];
      if (td && td.kind !== 'equal') {
        html += `<div class="diff-title-row"><span class="lbl">Titel</span><span class="ttl-from">${escapeHtml(td.from || '')}</span><span class="arr">→</span><span class="ttl-to">${escapeHtml(td.to || '')}</span></div>`;
      } else if (td) {
        html += `<div class="diff-title-row"><span class="lbl">Titel</span>${escapeHtml(td.from || '')}</div>`;
      }
      const lines = renderDiffLines(data.content_diff || []);
      if (!lines) {
        html += '<div class="diff-empty">Keine inhaltlichen Änderungen.</div>';
      } else {
        html += lines;
      }
      diffBody.innerHTML = html;
    } catch (err) {
      diffBody.innerHTML = '<div class="diff-empty">Diff laden fehlgeschlagen: ' + escapeHtml(String(err)) + '</div>';
    }
  }
  // ---------- Editor-UX ----------
  const docCharCount = document.getElementById('docCharCount');
  const docLineCount = document.getElementById('docLineCount');
  const docAutosaveToggle = document.getElementById('docAutosaveToggle');
  let autosaveOn = false;
  let autosaveTimer = null;

  function updateDocCounters() {
    const v = docContent.value;
    docCharCount.textContent = v.length + ' Zeichen';
    docLineCount.textContent = (v.split('\\n').length) + ' Zeilen';
  }
  function scheduleAutosave() {
    if (!autosaveOn) return;
    if (autosaveTimer) clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => {
      if (docDirty && !docContent.readOnly) saveDoc();
    }, 3000);
  }
  docAutosaveToggle.addEventListener('click', () => {
    autosaveOn = !autosaveOn;
    docAutosaveToggle.textContent = 'Auto-Save: ' + (autosaveOn ? 'an' : 'aus');
    docAutosaveToggle.classList.toggle('on', autosaveOn);
    if (autosaveOn) scheduleAutosave();
  });

  docTitle.addEventListener('input', () => { setDocDirty(true); scheduleAutosave(); });
  docContent.addEventListener('input', () => { setDocDirty(true); updateDocCounters(); scheduleAutosave(); });

  // Markdown-Helfer: arbeitet auf docContent.selectionStart/End
  function wrapSelection(before, after) {
    if (docContent.readOnly) return;
    const start = docContent.selectionStart;
    const end = docContent.selectionEnd;
    const sel = docContent.value.slice(start, end);
    const replacement = before + sel + after;
    docContent.setRangeText(replacement, start, end, 'end');
    if (!sel) {
      const pos = start + before.length;
      docContent.setSelectionRange(pos, pos);
    } else {
      docContent.setSelectionRange(start + before.length, start + before.length + sel.length);
    }
    docContent.focus();
    setDocDirty(true);
    updateDocCounters();
    scheduleAutosave();
  }
  function prefixLines(prefix) {
    if (docContent.readOnly) return;
    const v = docContent.value;
    const start = docContent.selectionStart;
    const end = docContent.selectionEnd;
    const lineStart = v.lastIndexOf('\\n', start - 1) + 1;
    let lineEnd = v.indexOf('\\n', end);
    if (lineEnd < 0) lineEnd = v.length;
    const block = v.slice(lineStart, lineEnd);
    const out = block.split('\\n').map((l, i) => {
      const p = typeof prefix === 'function' ? prefix(i) : prefix;
      return l.startsWith(p) ? l : p + l;
    }).join('\\n');
    docContent.setRangeText(out, lineStart, lineEnd, 'end');
    docContent.focus();
    setDocDirty(true);
    updateDocCounters();
    scheduleAutosave();
  }
  function applyMd(kind) {
    switch (kind) {
      case 'h1': prefixLines('# '); break;
      case 'h2': prefixLines('## '); break;
      case 'h3': prefixLines('### '); break;
      case 'bold': wrapSelection('**', '**'); break;
      case 'italic': wrapSelection('*', '*'); break;
      case 'code': wrapSelection('`', '`'); break;
      case 'ul': prefixLines('- '); break;
      case 'ol': prefixLines((i) => (i + 1) + '. '); break;
      case 'quote': prefixLines('> '); break;
      case 'link': wrapSelection('[', '](url)'); break;
      case 'codeblock': wrapSelection('\\n```\\n', '\\n```\\n'); break;
    }
  }
  document.getElementById('docToolbar').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-md]');
    if (!btn) return;
    e.preventDefault();
    applyMd(btn.dataset.md);
  });

  docContent.addEventListener('keydown', (e) => {
    // Save: Ctrl/Cmd+S (auch Ctrl/Cmd+Enter)
    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'Enter')) {
      e.preventDefault();
      if (docDirty && !docContent.readOnly) saveDoc();
      return;
    }
    if (docContent.readOnly) return;
    // Tab → 2 Spaces (oder Block-Indent bei Mehrzeilen-Selection)
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = docContent.selectionStart;
      const end = docContent.selectionEnd;
      const sel = docContent.value.slice(start, end);
      if (sel.includes('\\n')) {
        // Block-Indent / -Outdent
        if (e.shiftKey) {
          prefixLines(''); // no-op for safety
          // dedent: remove leading 2 spaces per line
          const v = docContent.value;
          const lineStart = v.lastIndexOf('\\n', start - 1) + 1;
          let lineEnd = v.indexOf('\\n', end);
          if (lineEnd < 0) lineEnd = v.length;
          const block = v.slice(lineStart, lineEnd);
          const out = block.split('\\n').map(l => l.startsWith('  ') ? l.slice(2) : l.startsWith('\\t') ? l.slice(1) : l).join('\\n');
          docContent.setRangeText(out, lineStart, lineEnd, 'end');
        } else {
          prefixLines('  ');
        }
      } else {
        if (e.shiftKey) {
          // dedent single line
          const v = docContent.value;
          const lineStart = v.lastIndexOf('\\n', start - 1) + 1;
          if (v.startsWith('  ', lineStart)) {
            docContent.setRangeText('', lineStart, lineStart + 2, 'preserve');
          }
        } else {
          docContent.setRangeText('  ', start, end, 'end');
        }
      }
      setDocDirty(true);
      updateDocCounters();
      scheduleAutosave();
      return;
    }
    // Markdown-Shortcuts
    if (e.ctrlKey || e.metaKey) {
      if (e.key === 'b' || e.key === 'B') { e.preventDefault(); applyMd('bold'); return; }
      if (e.key === 'i' || e.key === 'I') { e.preventDefault(); applyMd('italic'); return; }
      if (e.key === 'k' || e.key === 'K') { e.preventDefault(); applyMd('link'); return; }
    }
    // Enter: List-Continuation
    if (e.key === 'Enter' && !e.shiftKey) {
      const v = docContent.value;
      const start = docContent.selectionStart;
      const lineStart = v.lastIndexOf('\\n', start - 1) + 1;
      const currentLine = v.slice(lineStart, start);
      const ulMatch = currentLine.match(/^(\\s*)([-*+])\\s+/);
      const olMatch = currentLine.match(/^(\\s*)(\\d+)\\.\\s+/);
      if (ulMatch) {
        e.preventDefault();
        const rest = currentLine.slice(ulMatch[0].length);
        if (rest.trim() === '') {
          // Leerer Listenpunkt → Liste beenden
          docContent.setRangeText('', lineStart, start, 'end');
        } else {
          docContent.setRangeText('\\n' + ulMatch[1] + ulMatch[2] + ' ', start, start, 'end');
        }
        setDocDirty(true); updateDocCounters(); scheduleAutosave();
        return;
      }
      if (olMatch) {
        e.preventDefault();
        const rest = currentLine.slice(olMatch[0].length);
        if (rest.trim() === '') {
          docContent.setRangeText('', lineStart, start, 'end');
        } else {
          const next = parseInt(olMatch[2], 10) + 1;
          docContent.setRangeText('\\n' + olMatch[1] + next + '. ', start, start, 'end');
        }
        setDocDirty(true); updateDocCounters(); scheduleAutosave();
        return;
      }
    }
  });

  // Counter beim Öffnen aktualisieren — Hooks in openDoc/createDoc/viewDocVersion
  // werden über das input-Event ohnehin getriggert, aber beim Programm-Setzen
  // von docContent.value feuert input nicht — daher manuell nachziehen.
  const _origOpenDoc = openDoc;
  openDoc = async function(id) { await _origOpenDoc(id); updateDocCounters(); };
  const _origCreateDoc = createDoc;
  createDoc = async function() { await _origCreateDoc(); updateDocCounters(); };
  if (typeof viewDocVersion === 'function') {
    const _origViewDocVersion = viewDocVersion;
    viewDocVersion = async function(...args) { await _origViewDocVersion(...args); updateDocCounters(); };
  }

  // ---------- Aktionen ----------
  const actionToast = document.getElementById('actionToast');
  const actionToastTitle = document.getElementById('actionToastTitle');
  const actionToastBody = document.getElementById('actionToastBody');
  document.getElementById('actionToastClose').addEventListener('click', () => actionToast.classList.remove('open'));

  function showActionToast(title, body, isErr) {
    actionToastTitle.textContent = title;
    actionToastBody.textContent = body;
    actionToast.classList.toggle('err', !!isErr);
    actionToast.classList.add('open');
    setTimeout(() => actionToast.classList.remove('open'), 8000);
  }

  function renderActionButtons(container, actions, ctx) {
    container.innerHTML = '';
    if (!actions || actions.length === 0) {
      container.innerHTML = '<div class="action-empty">Keine Aktionen verfügbar.</div>';
      return;
    }
    for (const a of actions) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'action-btn' + (a.is_destructive ? ' destructive' : '');
      btn.title = a.description || '';
      let inner = '';
      if (a.icon) inner += '<span class="icon">' + escapeHtml(a.icon) + '</span>';
      let label = '<div class="label">' + escapeHtml(a.label);
      if (a.refine_reason) label += '<div class="reason">' + escapeHtml(a.refine_reason) + '</div>';
      label += '</div>';
      inner += label;
      if (a.needs_confirmation) inner += '<span class="confirm-mark">⚠</span>';
      btn.innerHTML = inner;
      btn.addEventListener('click', (e) => { e.stopPropagation(); runAction(a, ctx); });
      container.appendChild(btn);
    }
  }

  async function runAction(action, ctx) {
    if (action.needs_confirmation) {
      if (!confirm('Aktion "' + action.label + '" ausführen?')) return;
    }
    const body = {
      action_key: action.key,
      cls: (ctx && ctx.cls) || '',
      id: (ctx && ctx.id) || 0,
      chat_id: currentChatId || 0,
    };
    try {
      const r = await fetch(API('/actions/run'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const txt = await r.text();
        throw new Error('HTTP ' + r.status + ': ' + txt);
      }
      const data = await r.json();
      if (data.kind === 'chat_task') {
        await refreshSessions();
        await loadChat(data.chat_id);
        input.value = data.prompt;
        input.focus();
        showActionToast('Aktion vorbereitet', 'Chat #' + data.chat_id + ' geöffnet — sende ab, um den Manager-Agent zu starten.');
      } else if (data.kind === 'tool_call') {
        const out = typeof data.result === 'object' ? JSON.stringify(data.result, null, 2) : String(data.result);
        showActionToast(action.label + ' (Tool ausgeführt)', out);
        if (!document.getElementById('tab-mappe').classList.contains('hidden')) refreshMappe();
        if (!document.getElementById('tab-dokumente').classList.contains('hidden')) refreshDocs();
      } else {
        showActionToast('Unbekannter Action-Typ', JSON.stringify(data));
      }
    } catch (err) {
      showActionToast('Aktion fehlgeschlagen', String(err), true);
    }
    // Mappe-Popups zumachen
    for (const p of document.querySelectorAll('.action-popup.open')) p.classList.remove('open');
  }

  async function loadActions(container, query) {
    container.innerHTML = '<div class="action-loading">Lade…</div>';
    try {
      const params = new URLSearchParams();
      if (query.cls) params.set('cls', query.cls);
      if (query.id) params.set('id', String(query.id));
      if (query.refine) params.set('refine', 'true');
      const r = await fetch(API('/actions?' + params.toString()));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      renderActionButtons(container, data.actions || [], { cls: query.cls, id: query.id });
    } catch (err) {
      container.innerHTML = '<div class="action-empty">Fehler: ' + escapeHtml(String(err)) + '</div>';
    }
  }

  async function refreshDocActions(docId) {
    const container = document.getElementById('docActions');
    if (!docId) {
      container.innerHTML = '<div class="action-empty">Speichern, dann sind Aktionen verfügbar.</div>';
      return;
    }
    await loadActions(container, { cls: 'core.document', id: docId, refine: true });
  }

  // Hook docOverlay open: lade Doc-Aktionen
  const _origOpenDoc2 = openDoc;
  openDoc = async function(id) {
    await _origOpenDoc2(id);
    refreshDocActions(id);
  };
  const _origCreateDoc2 = createDoc;
  createDoc = async function() {
    await _origCreateDoc2();
    refreshDocActions(null);
  };
  const _origClose = closeDocOverlay;
  closeDocOverlay = function() {
    _origClose();
    document.getElementById('docActions').innerHTML = '<div class="action-empty">—</div>';
  };

  // ---------- Doc-Suche im Tab ----------
  const docSearchInput = document.getElementById('docSearch');
  let docSearchTimer = null;
  let allDocsCache = [];

  function renderDocList(docs) {
    const list = document.getElementById('docList');
    const empty = document.getElementById('docEmpty');
    list.innerHTML = '';
    if (!docs || docs.length === 0) {
      empty.style.display = '';
      empty.textContent = docSearchInput.value ? 'Keine Treffer.' : 'Noch keine Dokumente.';
      return;
    }
    empty.style.display = 'none';
    for (const d of docs) {
      const card = el('div', 'doc-card-item');
      card.innerHTML = `
        <div class="title">${escapeHtml(d.title)}</div>
        <div class="meta">
          <span class="v">v${d.version}</span>
          <span>${escapeHtml(d.author_display_name || '')}</span>
          <span>${fmtDate(d.updated_at)}</span>
        </div>
      `;
      card.addEventListener('click', () => openDoc(d.id));
      list.appendChild(card);
    }
  }

  // Override refreshDocs to cache + apply filter
  const _origRefreshDocs = refreshDocs;
  refreshDocs = async function() {
    try {
      const r = await fetch(API('/documents?limit=200'));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      allDocsCache = data.documents || [];
      applyDocFilter();
    } catch (err) {
      const empty = document.getElementById('docEmpty');
      document.getElementById('docList').innerHTML = '';
      empty.textContent = 'Laden fehlgeschlagen: ' + err;
      empty.style.display = '';
    }
  };

  function applyDocFilter() {
    const q = (docSearchInput.value || '').toLowerCase().trim();
    if (!q) return renderDocList(allDocsCache);
    const filtered = allDocsCache.filter(d =>
      (d.title || '').toLowerCase().includes(q) ||
      (d.author_display_name || '').toLowerCase().includes(q)
    );
    renderDocList(filtered);
  }

  docSearchInput.addEventListener('input', () => {
    if (docSearchTimer) clearTimeout(docSearchTimer);
    docSearchTimer = setTimeout(applyDocFilter, 120);
  });

  // ---------- Doc-Klick in Mappe ----------
  // Wenn die Mappe-Render-Funktion einen Bereich für Dokumente hat, klickbar machen.
  // Wir injizieren das via MutationObserver, damit wir den Mappe-Render-Code nicht anfassen.
  const mappeContent = document.getElementById('mappeContent');
  if (mappeContent) {
    new MutationObserver(() => {
      for (const card of mappeContent.querySelectorAll('[data-doc-id]:not([data-doc-wired])')) {
        const id = parseInt(card.dataset.docId, 10);
        if (!id) continue;
        card.setAttribute('data-doc-wired', '1');
        card.classList.add('clickable');
        card.addEventListener('click', () => openDoc(id));
      }
    }).observe(mappeContent, { childList: true, subtree: true });
  }

  // ---------- Chat-Kontext / Quick-Actions über dem Input ----------
  let currentArtifact = null;
  const chatCtxBar = document.getElementById('chatContext');
  const chatCtxLabel = document.getElementById('chatContextLabel');
  const chatCtxPills = document.getElementById('chatContextActions');
  document.getElementById('chatContextClear').addEventListener('click', clearChatContext);

  function clearChatContext() {
    currentArtifact = null;
    chatCtxBar.classList.remove('open');
    chatCtxPills.innerHTML = '';
    chatCtxLabel.innerHTML = '';
  }

  async function setChatContext(cls, id, label) {
    if (!cls || !id) return clearChatContext();
    currentArtifact = { cls, id, label };
    chatCtxLabel.innerHTML = '<span>' + escapeHtml(label) + '</span><span class="cls">' + escapeHtml(cls) + ' #' + id + '</span>';
    chatCtxPills.innerHTML = '<div class="action-loading">Lade…</div>';
    chatCtxBar.classList.add('open');
    try {
      const r = await fetch(API('/actions?cls=' + encodeURIComponent(cls) + '&id=' + id + '&refine=true&limit=4'));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      chatCtxPills.innerHTML = '';
      for (const a of (data.actions || []).slice(0, 4)) {
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = 'pill' + (a.is_destructive ? ' destructive' : '');
        pill.textContent = (a.icon ? a.icon + ' ' : '') + a.label;
        pill.title = a.description || '';
        pill.addEventListener('click', () => runAction(a, { cls, id }));
        chatCtxPills.appendChild(pill);
      }
      if (!chatCtxPills.children.length) {
        chatCtxPills.innerHTML = '<span style="color:#5a5d65">Keine Aktionen verfügbar.</span>';
      }
    } catch (err) {
      chatCtxPills.innerHTML = '<span style="color:#f08080">Fehler: ' + escapeHtml(String(err)) + '</span>';
    }
  }

  // Hooks: openDoc / openEntityOverlay setzen den Chat-Kontext
  const _origOpenDoc3 = openDoc;
  openDoc = async function(id) {
    await _origOpenDoc3(id);
    const title = (docTitle && docTitle.value) ? docTitle.value : ('Dokument #' + id);
    setChatContext('core.document', id, title);
  };
  if (typeof openEntityOverlay === 'function') {
    const _origOpenEntityOverlay = openEntityOverlay;
    openEntityOverlay = function(cls, id, label) {
      _origOpenEntityOverlay(cls, id, label);
      const fullCls = cls.startsWith('crm.') ? cls : ('crm.' + cls);
      setChatContext(fullCls, id, label || (cls + ' #' + id));
    };
  }

  // ---------- init ----------
  (async () => {
    await refreshSessions();
    const deepId = chatIdFromUrl();
    if (deepId) await loadChat(deepId, { updateUrl: false });
  })();
</script>
</body>
</html>
"""
