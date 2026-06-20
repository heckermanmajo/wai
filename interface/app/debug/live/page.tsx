"use client";

import { useEffect, useRef, useState } from "react";
import styles from "../debug.module.css";

type LiveEvent = {
  id: string;
  ts: number;
  type: string;
  payload: string;
};

export default function DebugLivePage() {
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/api/debug/stream", { withCredentials: true } as EventSourceInit);
    esRef.current = es;

    es.onopen = () => setStatus("open");
    es.onerror = () => setStatus("closed");
    es.addEventListener("ready", (ev) => {
      setEvents((prev) => [
        {
          id: `ready-${Date.now()}`,
          ts: Date.now(),
          type: "ready",
          payload: (ev as MessageEvent).data || "",
        },
        ...prev,
      ]);
    });
    es.onmessage = (ev) => {
      setEvents((prev) => [
        {
          id: `msg-${Date.now()}-${prev.length}`,
          ts: Date.now(),
          type: "message",
          payload: ev.data || "",
        },
        ...prev.slice(0, 199),
      ]);
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, []);

  return (
    <div className={styles.content}>
      <div className={styles.toolbar}>
        <span>Status:</span>
        <span
          className={
            status === "open"
              ? styles.pillOnline
              : status === "connecting"
              ? styles.pillRunning
              : styles.pillOffline
          }
        >
          {status}
        </span>
        <span className={styles.mono} style={{ marginLeft: "auto" }}>
          {events.length} Events
        </span>
      </div>
      <div className={styles.list}>
        <div className={styles.liveBox}>
          <p>
            Live-Stream V1 — Verbindung steht, Events werden gestreamt sobald der
            globale EventBroker-Multiplexer aktiv ist (Sub-Iteration 2 von Plan 06).
            Heartbeat alle 15s haelt die SSE-Verbindung offen.
          </p>
        </div>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Zeit</th>
              <th>Typ</th>
              <th>Payload</th>
            </tr>
          </thead>
          <tbody>
            {events.length === 0 && (
              <tr><td colSpan={3} className={styles.empty}>Warte auf Events…</td></tr>
            )}
            {events.map((ev) => (
              <tr key={ev.id}>
                <td className={styles.mono}>{new Date(ev.ts).toLocaleTimeString("de-DE")}</td>
                <td className={styles.mono}>{ev.type}</td>
                <td>
                  <pre style={{ margin: 0, fontSize: 11, maxHeight: 80, overflow: "auto" }}>
                    {ev.payload}
                  </pre>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
