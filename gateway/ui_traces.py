"""HTML-UI für den Trace-Browser (Stufe 3).

Eine einzige Seite — links Tabelle aller Traces (filterbar nach Tenant/
Status), rechts Detail-Pane mit voller Event-Timeline des selektierten
Trace. Hash-Routing: /traces#<uid> öffnet direkt diesen Trace.
"""

TRACES_HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<title>wai · traces</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    font: 14px/1.5 -apple-system, system-ui, sans-serif;
    margin: 0; background: #0e0f12; color: #e8eaed; height: 100vh;
    display: flex; flex-direction: column;
  }
  header {
    padding: 12px 18px; border-bottom: 1px solid #25262b;
    display: flex; justify-content: space-between; align-items: center;
    font-weight: 600;
  }
  header small { color: #7c818b; font-weight: 400; margin-left: 6px; }
  .nav-link {
    color: #82b1ff; text-decoration: none; font-size: 12px;
    font-family: ui-monospace, monospace;
  }
  .nav-link:hover { text-decoration: underline; }
  #layout { flex: 1; display: flex; min-height: 0; }
  #list { flex: 1.4; border-right: 1px solid #25262b; display: flex; flex-direction: column; min-width: 0; }
  #detail { flex: 1; display: flex; flex-direction: column; min-width: 0; background: #0c0d10; }
  .toolbar {
    display: flex; gap: 8px; align-items: center; padding: 10px 14px;
    border-bottom: 1px solid #1c1d22; font-size: 12px; flex-wrap: wrap;
  }
  .toolbar label { color: #7c818b; }
  .toolbar input, .toolbar select {
    background: #1a1c20; color: #e8eaed; border: 1px solid #2d2f36;
    border-radius: 4px; padding: 4px 8px; font: inherit;
  }
  .toolbar button {
    background: #2d2f36; color: #e8eaed; border: none; border-radius: 4px;
    padding: 4px 10px; cursor: pointer; font: inherit;
  }
  .toolbar button:hover { background: #3a3d46; }
  .toolbar .right { margin-left: auto; color: #7c818b; }
  .table-wrap { flex: 1; overflow: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  thead th {
    position: sticky; top: 0; background: #16181d; z-index: 1;
    text-align: left; padding: 8px 10px; color: #9aa0aa; font-weight: 500;
    border-bottom: 1px solid #23262d; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.05em;
  }
  tbody td {
    padding: 7px 10px; border-bottom: 1px solid #1a1c20;
    vertical-align: top; word-break: break-word;
  }
  tbody tr { cursor: pointer; }
  tbody tr:hover { background: #14161a; }
  tbody tr.selected { background: #18223a; }
  tbody tr.selected td { color: #cfe1ff; }
  .uid { font-family: ui-monospace, monospace; color: #82b1ff; font-size: 11px; }
  .pill {
    display: inline-block; padding: 1px 7px; border-radius: 10px;
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .pill.ok { background: #1f3a26; color: #7ed99c; }
  .pill.error { background: #3a1f1f; color: #f08080; }
  .pill.running { background: #1f2532; color: #82b1ff; }
  .pill.intent {
    background: #2a2230; color: #b39ddb; font-weight: 500;
  }
  .pill.intent.muted { background: transparent; color: #5a5d65; }
  .preview { color: #c5cad3; font-size: 12px; }

  /* Detail-Pane */
  .detail-empty {
    flex: 1; display: flex; align-items: center; justify-content: center;
    color: #5a5d65; font-style: italic;
  }
  .detail-head {
    padding: 14px 18px; border-bottom: 1px solid #1c1d22;
  }
  .detail-head .uid {
    font-size: 12px; color: #82b1ff; font-family: ui-monospace, monospace;
    word-break: break-all;
  }
  .detail-head .summary {
    margin-top: 6px; color: #e8eaed; font-size: 13px; word-break: break-word;
  }
  .detail-head .response {
    margin-top: 6px; color: #9aa0aa; font-size: 12px; word-break: break-word;
    max-height: 80px; overflow: auto;
    border-left: 2px solid #2d2f36; padding-left: 8px;
  }
  .detail-stats {
    padding: 8px 18px; border-bottom: 1px solid #1c1d22;
    display: flex; gap: 16px; flex-wrap: wrap;
    color: #9aa0aa; font-family: ui-monospace, monospace; font-size: 11px;
  }
  .detail-stats b { color: #e8eaed; }
  .detail-filter {
    padding: 8px 18px; border-bottom: 1px solid #1c1d22;
    display: flex; gap: 6px; flex-wrap: wrap; font-size: 11px;
  }
  .filter-chip {
    padding: 2px 8px; border-radius: 10px; background: #16181d;
    border: 1px solid #2d2f36; cursor: pointer; color: #9aa0aa;
    font-family: ui-monospace, monospace; font-size: 10px;
  }
  .filter-chip.active { background: #1f2532; border-color: #4669ff; color: #cfe1ff; }
  .detail-events { flex: 1; overflow-y: auto; }
  .ev-row {
    padding: 7px 18px; border-left: 3px solid transparent;
    font-family: ui-monospace, SFMono-Regular, monospace; font-size: 11px;
    border-bottom: 1px solid #1a1c20;
  }
  .ev-row .row1 {
    display: flex; justify-content: space-between; gap: 8px;
  }
  .ev-row .type { font-weight: 600; }
  .ev-row .meta { color: #6a6e76; font-size: 10px; }
  .ev-row .body { color: #c5cad3; margin-top: 3px; word-break: break-word; }
  .ev-row .body code {
    background: #1a1c20; padding: 1px 4px; border-radius: 3px; color: #cfe1ff;
  }
  .ev-row.t-trace_started { border-left-color: #7c818b; }
  .ev-row.t-intent_classified { border-left-color: #82b1ff; }
  .ev-row.t-intent_classified .type { color: #82b1ff; }
  .ev-row.t-mcp_connected { border-left-color: #b39ddb; }
  .ev-row.t-mcp_connected .type { color: #b39ddb; }
  .ev-row.t-llm_request { border-left-color: #4a5468; }
  .ev-row.t-llm_request .type { color: #8a94a8; }
  .ev-row.t-llm_response { border-left-color: #7ed99c; }
  .ev-row.t-llm_response .type { color: #7ed99c; }
  .ev-row.t-tool_call_started { border-left-color: #f0c674; }
  .ev-row.t-tool_call_started .type { color: #f0c674; }
  .ev-row.t-tool_call_result { border-left-color: #d4a45a; }
  .ev-row.t-tool_call_result .type { color: #d4a45a; }
  .ev-row.t-error { border-left-color: #f08080; background: #1d1010; }
  .ev-row.t-error .type { color: #f08080; }
  .ev-row.t-trace_completed { border-left-color: #7ed99c; background: #0e1810; }
  .ev-row.t-trace_completed .type { color: #7ed99c; }
  .ev-row.hidden { display: none; }
</style>
</head>
<body>
<header>
  <span>wai · traces <small>· event-browser</small></span>
  <span><a class="nav-link" href="/">← /chat</a></span>
</header>
<div id="layout">
  <div id="list">
    <div class="toolbar">
      <label>Tenant <input id="fTenant" type="text" size="10" placeholder="alle" /></label>
      <label>Status
        <select id="fStatus">
          <option value="">alle</option>
          <option value="ok">ok</option>
          <option value="error">error</option>
          <option value="running">running</option>
        </select>
      </label>
      <label>Limit <input id="fLimit" type="number" min="10" max="500" value="50" style="width:70px" /></label>
      <button id="fReload" type="button">Neu laden</button>
      <span class="right" id="fCount">—</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Zeit</th>
            <th>Trace</th>
            <th>Tenant</th>
            <th>Status</th>
            <th>Intent</th>
            <th>ms</th>
            <th>Tools</th>
            <th>Events</th>
            <th>User-Message</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>
  <div id="detail">
    <div class="detail-empty" id="detailEmpty">Wähle links einen Trace, um die Events zu sehen.</div>
    <div id="detailContent" style="display:none; flex:1; display:none; flex-direction:column; min-height:0">
      <div class="detail-head">
        <div class="uid" id="dUid"></div>
        <div class="summary" id="dSummary"></div>
        <div class="response" id="dResponse" style="display:none"></div>
      </div>
      <div class="detail-stats" id="dStats"></div>
      <div class="detail-filter" id="dFilter"></div>
      <div class="detail-events" id="dEvents"></div>
    </div>
  </div>
</div>
<script>
  const tbody = document.getElementById('tbody');
  const fTenant = document.getElementById('fTenant');
  const fStatus = document.getElementById('fStatus');
  const fLimit = document.getElementById('fLimit');
  const fReload = document.getElementById('fReload');
  const fCount = document.getElementById('fCount');
  const detailEmpty = document.getElementById('detailEmpty');
  const detailContent = document.getElementById('detailContent');
  const dUid = document.getElementById('dUid');
  const dSummary = document.getElementById('dSummary');
  const dResponse = document.getElementById('dResponse');
  const dStats = document.getElementById('dStats');
  const dFilter = document.getElementById('dFilter');
  const dEvents = document.getElementById('dEvents');

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
      {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
    ));
  }

  function fmtTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString([], { hour12: false });
  }

  async function loadTraces() {
    const params = new URLSearchParams();
    const tenant = fTenant.value.trim();
    if (tenant) params.set('tenant_id', tenant);
    if (fStatus.value) params.set('status', fStatus.value);
    params.set('limit', String(parseInt(fLimit.value || '50', 10)));
    const resp = await fetch('/api/traces?' + params.toString());
    if (!resp.ok) {
      tbody.innerHTML = `<tr><td colspan="9" style="color:#f08080">Fehler ${resp.status}</td></tr>`;
      return;
    }
    const data = await resp.json();
    renderList(data.traces || []);
    fCount.textContent = `${(data.traces || []).length} Treffer`;
  }

  function renderList(rows) {
    tbody.innerHTML = '';
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="color:#5a5d65">Keine Traces.</td></tr>';
      return;
    }
    rows.forEach(t => {
      const tr = el('tr');
      tr.dataset.uid = t.trace_uid;
      tr.addEventListener('click', () => selectTrace(t.trace_uid));
      tr.appendChild(el('td', null, fmtTime(t.started_at)));
      const uidTd = el('td');
      uidTd.appendChild(el('span', 'uid', t.trace_uid.slice(0, 8)));
      tr.appendChild(uidTd);
      tr.appendChild(el('td', null, t.tenant_id));
      const statusTd = el('td');
      statusTd.appendChild(el('span', 'pill ' + (t.status || 'running'), t.status || 'running'));
      tr.appendChild(statusTd);
      const intentTd = el('td');
      intentTd.appendChild(el('span', 'pill intent' + (t.intent ? '' : ' muted'), t.intent || '—'));
      tr.appendChild(intentTd);
      tr.appendChild(el('td', null, String(t.duration_ms || 0)));
      tr.appendChild(el('td', null, String(t.tool_call_count || 0)));
      tr.appendChild(el('td', null, String(t.event_count || 0)));
      const msgTd = el('td', 'preview', (t.user_message || '').slice(0, 80));
      tr.appendChild(msgTd);
      tbody.appendChild(tr);
    });
  }

  let currentUid = null;
  let currentEvents = [];
  const activeFilters = new Set();

  async function selectTrace(uid) {
    currentUid = uid;
    history.replaceState(null, '', '#' + encodeURIComponent(uid));
    document.querySelectorAll('tbody tr.selected').forEach(r => r.classList.remove('selected'));
    const row = document.querySelector(`tbody tr[data-uid="${uid}"]`);
    if (row) row.classList.add('selected');
    detailEmpty.style.display = 'none';
    detailContent.style.display = 'flex';
    dUid.textContent = uid;
    dSummary.textContent = 'Lade…';
    dStats.innerHTML = '';
    dFilter.innerHTML = '';
    dEvents.innerHTML = '';
    const resp = await fetch('/api/traces/' + encodeURIComponent(uid));
    if (!resp.ok) {
      dSummary.innerHTML = `<span style="color:#f08080">Fehler ${resp.status}</span>`;
      return;
    }
    const payload = await resp.json();
    renderDetail(payload.trace, payload.events || []);
  }

  function renderDetail(trace, events) {
    currentEvents = events;
    activeFilters.clear();
    dSummary.textContent = trace.user_message || '';
    if (trace.response) {
      dResponse.textContent = trace.response;
      dResponse.style.display = '';
    } else {
      dResponse.style.display = 'none';
    }
    const fields = [
      ['Status', trace.status],
      ['Intent', trace.intent || '—'],
      ['Tenant', trace.tenant_id],
      ['Dauer', (trace.duration_ms || 0) + ' ms'],
      ['Events', trace.event_count],
      ['Tool-Calls', trace.tool_call_count],
      ['Start', fmtTime(trace.started_at)],
      ['Ende', fmtTime(trace.finished_at)],
    ];
    dStats.innerHTML = fields.map(([k, v]) => `${k} <b>${esc(v)}</b>`).join(' · ');

    const types = [...new Set(events.map(e => e.event_type))];
    types.forEach(t => {
      const chip = el('span', 'filter-chip', t);
      chip.addEventListener('click', () => {
        if (activeFilters.has(t)) {
          activeFilters.delete(t);
          chip.classList.remove('active');
        } else {
          activeFilters.add(t);
          chip.classList.add('active');
        }
        applyFilter();
      });
      dFilter.appendChild(chip);
    });

    dEvents.innerHTML = '';
    events.forEach(e => dEvents.appendChild(renderEvent(e)));
  }

  function applyFilter() {
    dEvents.querySelectorAll('.ev-row').forEach(r => {
      if (activeFilters.size === 0 || activeFilters.has(r.dataset.type)) {
        r.classList.remove('hidden');
      } else {
        r.classList.add('hidden');
      }
    });
  }

  function renderEvent(ev) {
    const div = el('div', 'ev-row t-' + ev.event_type);
    div.dataset.type = ev.event_type;
    const row1 = el('div', 'row1');
    row1.appendChild(el('span', 'type', ev.event_type));
    row1.appendChild(el('span', 'meta', '#' + ev.sequence + ' · ' + fmtTime(ev.timestamp)));
    div.appendChild(row1);
    const body = describeEvent(ev);
    if (body) {
      const bodyEl = el('div', 'body');
      bodyEl.innerHTML = body;
      div.appendChild(bodyEl);
    }
    return div;
  }

  function describeEvent(ev) {
    const d = ev.data || {};
    switch (ev.event_type) {
      case 'trace_started':
        return `tenant=<code>${esc(d.tenant_id || '')}</code> · history_len=${d.history_len}<br><span style="color:#9aa0aa">${esc(d.user_message || '')}</span>`;
      case 'intent_classified': {
        const tok = d.prompt_tokens != null ? ` · ${d.prompt_tokens}+${d.completion_tokens || 0}tok` : '';
        return `intent=<code>${esc(d.intent || '')}</code> · ${d.duration_ms}ms · model=<code>${esc(d.model || '')}</code>${tok}`;
      }
      case 'mcp_connected':
        return `${esc(d.url || '')}<br>tools=[${(d.tool_names || []).map(esc).join(', ')}]`;
      case 'llm_request':
        return `round=${d.round} · model=<code>${esc(d.model || '')}</code> · msgs=${d.messages_count} · tools=${d.has_tools}`;
      case 'llm_response': {
        const tok = d.prompt_tokens != null ? ` · ${d.prompt_tokens}+${d.completion_tokens || 0}tok` : '';
        const tc = d.has_tool_calls ? ' · → ruft Tools' : '';
        const preview = d.content_preview ? `<br><span style="color:#9aa0aa">${esc(d.content_preview)}</span>` : '';
        return `${d.duration_ms}ms${tok}${tc}${preview}`;
      }
      case 'tool_call_started':
        return `<code>${esc(d.tool_name || '')}</code>(${esc(JSON.stringify(d.args || {}))})`;
      case 'tool_call_result': {
        const err = d.is_error ? ' <span style="color:#f08080">ERROR</span>' : '';
        const preview = d.result_preview ? `<br><span style="color:#9aa0aa">${esc(d.result_preview)}</span>` : '';
        return `<code>${esc(d.tool_name || '')}</code> · ${d.duration_ms}ms${err}${preview}`;
      }
      case 'error':
        return `<code>${esc(d.error_type || '')}</code> ${esc(d.message || '')}`;
      case 'trace_completed':
        return `status=<code>${esc(d.status || '')}</code> · ${d.total_duration_ms}ms`;
      default:
        return esc(JSON.stringify(d));
    }
  }

  fReload.addEventListener('click', loadTraces);
  fTenant.addEventListener('change', loadTraces);
  fStatus.addEventListener('change', loadTraces);
  fLimit.addEventListener('change', loadTraces);

  loadTraces().then(() => {
    const hash = window.location.hash.replace(/^#/, '');
    if (hash) selectTrace(decodeURIComponent(hash));
  });

  // Auto-Refresh alle 10s, wenn kein Trace selektiert ist
  setInterval(() => { if (!currentUid) loadTraces(); }, 10000);
</script>
</body>
</html>
"""
