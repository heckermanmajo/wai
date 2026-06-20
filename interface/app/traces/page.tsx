"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchTrace, fetchTraces } from "@/lib/api/traces";
import type { TraceDetailResponse, TraceEventDto, TraceRow } from "@/lib/api/types";
import styles from "./traces.module.css";

const EVENT_COLORS: Record<string, string> = {
  trace_started: "#82b1ff",
  intent_classified: "#82b1ff",
  mcp_connected: "#82b1ff",
  llm_request: "#4a5468",
  llm_response: "#7ed99c",
  tool_call_started: "#f0c674",
  tool_call_result: "#d4a45a",
  error: "#f08080",
  trace_completed: "#7ed99c",
};

export default function TracesPage() {
  const [rows, setRows] = useState<TraceRow[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [status, setStatus] = useState("");
  const [limit, setLimit] = useState(50);
  const [selectedUid, setSelectedUid] = useState<string>("");
  const [detail, setDetail] = useState<TraceDetailResponse | null>(null);
  const [eventFilter, setEventFilter] = useState<Set<string>>(new Set());

  const reload = useCallback(() => {
    fetchTraces({
      tenant_id: tenantId.trim() || undefined,
      status: status || undefined,
      limit,
    }).then((r) => setRows(r.traces)).catch(() => {});
  }, [tenantId, status, limit]);

  // Hash-Routing
  useEffect(() => {
    function syncHash() {
      const h = window.location.hash.replace(/^#/, "");
      setSelectedUid(h);
    }
    syncHash();
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  // Initial-Load + Filter-Wechsel
  useEffect(() => reload(), [reload]);

  // Auto-Refresh 10s wenn nichts selektiert
  useEffect(() => {
    if (selectedUid) return;
    const id = setInterval(reload, 10000);
    return () => clearInterval(id);
  }, [selectedUid, reload]);

  // Detail laden
  useEffect(() => {
    if (!selectedUid) {
      setDetail(null);
      return;
    }
    fetchTrace(selectedUid)
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [selectedUid]);

  function toggleEventFilter(type: string) {
    setEventFilter((s) => {
      const next = new Set(s);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <strong>wai · Traces</strong>
        <a href="/" className={styles.back}>← zurueck</a>
      </header>

      <div className={styles.body}>
        <section className={styles.list}>
          <div className={styles.toolbar}>
            <input
              placeholder="tenant_id"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              className={styles.filter}
            />
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">alle Status</option>
              <option value="ok">ok</option>
              <option value="error">error</option>
              <option value="running">running</option>
            </select>
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
              {[10, 25, 50, 100, 250, 500].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
            <button onClick={reload}>Reload</button>
          </div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Zeit</th>
                <th>UID</th>
                <th>Tenant</th>
                <th>Status</th>
                <th>Intent</th>
                <th>ms</th>
                <th>Tools</th>
                <th>Events</th>
                <th>User-Msg</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr><td colSpan={9} className={styles.empty}>Keine Traces</td></tr>
              )}
              {rows.map((r) => (
                <tr
                  key={r.trace_uid}
                  data-selected={selectedUid === r.trace_uid ? "1" : "0"}
                  onClick={() => {
                    window.location.hash = "#" + r.trace_uid;
                  }}
                >
                  <td className={styles.mono}>
                    {r.started_at ? new Date(r.started_at).toLocaleTimeString("de-DE") : "-"}
                  </td>
                  <td className={styles.mono}>{r.trace_uid.slice(0, 8)}</td>
                  <td>{r.tenant_id}</td>
                  <td><span className={styles.pill} data-status={r.status}>{r.status}</span></td>
                  <td><span className={styles.pill} data-intent="1">{r.intent || "-"}</span></td>
                  <td className={styles.mono}>{r.duration_ms}</td>
                  <td className={styles.mono}>{r.tool_call_count}</td>
                  <td className={styles.mono}>{r.event_count}</td>
                  <td className={styles.msg}>{r.user_message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {selectedUid && (
          <section className={styles.detail}>
            <header className={styles.detailHead}>
              <strong>{selectedUid.slice(0, 12)}…</strong>
              <button onClick={() => { window.location.hash = ""; }}>×</button>
            </header>
            {!detail && <div className={styles.loading}>Laedt…</div>}
            {detail && (
              <>
                <div className={styles.summary}>
                  <div><b>User:</b> {detail.trace.user_message}</div>
                  <div><b>Response:</b> {detail.trace.response}</div>
                  <div className={styles.stats}>
                    <span><b>Status:</b> {detail.trace.status}</span>
                    <span><b>Intent:</b> {detail.trace.intent || "-"}</span>
                    <span><b>Dauer:</b> {detail.trace.duration_ms}ms</span>
                    <span><b>Events:</b> {detail.trace.event_count}</span>
                    <span><b>Tools:</b> {detail.trace.tool_call_count}</span>
                  </div>
                </div>

                <div className={styles.filters}>
                  {Array.from(new Set(detail.events.map((e) => e.event_type))).map((t) => (
                    <button
                      key={t}
                      data-active={eventFilter.has(t) ? "1" : "0"}
                      onClick={() => toggleEventFilter(t)}
                      style={{ borderColor: EVENT_COLORS[t] }}
                    >
                      {t}
                    </button>
                  ))}
                  {eventFilter.size > 0 && (
                    <button onClick={() => setEventFilter(new Set())}>Alle</button>
                  )}
                </div>

                <ol className={styles.timeline}>
                  {detail.events
                    .filter((e) => eventFilter.size === 0 || eventFilter.has(e.event_type))
                    .map((e) => (
                      <EventEntry key={e.sequence} ev={e} />
                    ))}
                </ol>
              </>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function EventEntry({ ev }: { ev: TraceEventDto }) {
  return (
    <li className={styles.ev} style={{ borderLeftColor: EVENT_COLORS[ev.event_type] ?? "#444" }}>
      <div className={styles.evRow1}>
        <span className={styles.evType}>{ev.event_type}</span>
        <span className={styles.evSeq}>#{ev.sequence} · {new Date(ev.timestamp).toLocaleTimeString("de-DE")}</span>
      </div>
      <pre className={styles.evBody}>{JSON.stringify(ev.data, null, 2)}</pre>
    </li>
  );
}
