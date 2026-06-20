"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchDebugTrace } from "@/lib/api/debug";
import type { TraceDetailResponse, TraceEventDto } from "@/lib/api/types";
import styles from "../../debug.module.css";

const EVENT_COLORS: Record<string, string> = {
  trace_started: "#82b1ff",
  intent_classified: "#82b1ff",
  mcp_connected: "#82b1ff",
  llm_request: "#4a5468",
  llm_response: "#7ed99c",
  tool_call_started: "#f0c674",
  tool_call_result: "#d4a45a",
  sub_agent_started: "#c699f0",
  sub_agent_completed: "#c699f0",
  error: "#f08080",
  trace_completed: "#7ed99c",
};

export default function DebugTraceDetailPage() {
  const params = useParams<{ uid: string }>();
  const uid = params?.uid || "";
  const [detail, setDetail] = useState<TraceDetailResponse | null>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    if (!uid) return;
    fetchDebugTrace(uid)
      .then(setDetail)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [uid]);

  if (err) return <div className={styles.error}>{err}</div>;
  if (!detail) return <div className={styles.empty}>Laedt…</div>;

  return (
    <div className={styles.detailGrid}>
      <aside className={styles.detailSide}>
        <div className={styles.detailRow}><b>UID</b><span>{uid}</span></div>
        <div className={styles.detailRow}><b>Tenant</b><span>{detail.trace.tenant_id}</span></div>
        <div className={styles.detailRow}><b>Status</b><span>{detail.trace.status}</span></div>
        <div className={styles.detailRow}><b>Intent</b><span>{detail.trace.intent || "-"}</span></div>
        <div className={styles.detailRow}><b>Dauer</b><span>{detail.trace.duration_ms} ms</span></div>
        <div className={styles.detailRow}><b>Events</b><span>{detail.trace.event_count}</span></div>
        <div className={styles.detailRow}><b>Tools</b><span>{detail.trace.tool_call_count}</span></div>
        <div className={styles.detailRow}><b>Start</b><span>{detail.trace.started_at}</span></div>
        <div className={styles.detailRow}><b>Ende</b><span>{detail.trace.finished_at}</span></div>
        <Link href="/debug/traces" className={styles.mono} style={{ display: "block", marginTop: 12 }}>
          ← zur Liste
        </Link>
      </aside>
      <main className={styles.detailMain}>
        <div style={{ marginBottom: 12 }}>
          <div><b>User-Message:</b></div>
          <pre style={{ whiteSpace: "pre-wrap", margin: "4px 0" }}>{detail.trace.user_message}</pre>
          <div style={{ marginTop: 8 }}><b>Response:</b></div>
          <pre style={{ whiteSpace: "pre-wrap", margin: "4px 0" }}>{detail.trace.response}</pre>
        </div>
        <ol style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {detail.events.map((e) => (
            <EventCard key={e.sequence} ev={e} />
          ))}
        </ol>
      </main>
    </div>
  );
}

function EventCard({ ev }: { ev: TraceEventDto }) {
  const subTrace =
    (ev.event_type === "sub_agent_started" || ev.event_type === "sub_agent_completed")
      ? (ev.data as Record<string, unknown>)?.sub_trace_uid
      : null;
  return (
    <li
      style={{
        background: "var(--bg-tertiary)",
        borderLeft: `3px solid ${EVENT_COLORS[ev.event_type] ?? "#444"}`,
        padding: "6px 10px",
        borderRadius: 4,
        marginBottom: 4,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
        <span style={{ color: "var(--fg-primary)" }}>{ev.event_type}</span>
        <span style={{ color: "var(--fg-tertiary)" }}>
          #{ev.sequence} · {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString("de-DE") : ""}
        </span>
      </div>
      {typeof subTrace === "string" && subTrace && (
        <div style={{ fontSize: 11, marginTop: 2 }}>
          <Link href={`/debug/traces/${subTrace}`}>→ Sub-Trace oeffnen</Link>
        </div>
      )}
      <pre style={{
        margin: "4px 0 0",
        background: "var(--code-bg)",
        padding: "6px 8px",
        borderRadius: 4,
        fontSize: 11,
        color: "var(--fg-secondary)",
        maxHeight: 200,
        overflow: "auto",
      }}>
        {JSON.stringify(ev.data, null, 2)}
      </pre>
    </li>
  );
}
