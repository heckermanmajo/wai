"use client";

import { useChatStore } from "@/lib/store/useChatStore";
import styles from "./DebugPanel.module.css";

const EVENT_COLORS: Record<string, string> = {
  intent_classified: "#82b1ff",
  mcp_connected: "#82b1ff",
  llm_request: "#4a5468",
  llm_response: "#7ed99c",
  tool_call_started: "#f0c674",
  tool_call_result: "#d4a45a",
  error: "#f08080",
  trace_completed: "#7ed99c",
  trace_started: "#82b1ff",
};

export function DebugPanel() {
  const events = useChatStore((s) => s.debugEvents);
  const stats = useChatStore((s) => s.debugStats);
  const stream = useChatStore((s) => s.streaming);

  return (
    <aside className={styles.panel}>
      <div className={styles.head}>
        <strong>Debug · Live-Events</strong>
        {stream?.traceUid && <span className={styles.uid}>{stream.traceUid.slice(0, 8)}…</span>}
        {stream?.traceUid && (
          <a className={styles.detail} href={`/traces#${stream.traceUid}`} target="_blank" rel="noopener noreferrer">
            Detail ↗
          </a>
        )}
      </div>
      <div className={styles.stats}>
        <span>Events: {stats.events}</span>
        <span>LLM: {stats.llm}</span>
        <span>Tools: {stats.tools}</span>
        <span>Tokens: {stats.tokens}</span>
        <span>{stats.ms} ms</span>
      </div>
      <div className={styles.events}>
        {events.length === 0 && <div className={styles.empty}>Keine Events</div>}
        {events.map((ev) => (
          <div
            key={`${ev.sequence}-${ev.event_type}`}
            className={styles.ev}
            style={{ borderLeftColor: EVENT_COLORS[ev.event_type] ?? "#444" }}
          >
            <div className={styles.row1}>
              <span className={styles.type}>{ev.event_type}</span>
              <span className={styles.seq}>#{ev.sequence}</span>
            </div>
            <pre className={styles.body}>{JSON.stringify(ev.data, null, 0)}</pre>
          </div>
        ))}
      </div>
    </aside>
  );
}
