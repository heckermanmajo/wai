"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  fetchDebugMcp,
  fetchDebugMcpCalls,
  type DebugMcpCall,
  type DebugMcpEntry,
} from "@/lib/api/debug";
import styles from "../../debug.module.css";

export default function DebugMcpDetailPage() {
  const params = useParams<{ name: string }>();
  const name = params?.name || "";
  const [mcp, setMcp] = useState<DebugMcpEntry | null>(null);
  const [calls, setCalls] = useState<DebugMcpCall[]>([]);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    if (!name) return;
    setErr("");
    fetchDebugMcp(name)
      .then(setMcp)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
    fetchDebugMcpCalls(name, 50)
      .then((r) => setCalls(r.calls))
      .catch(() => {});
  }, [name]);

  if (err) return <div className={styles.error}>{err}</div>;
  if (!mcp) return <div className={styles.empty}>Laedt…</div>;

  return (
    <div className={styles.detailGrid}>
      <aside className={styles.detailSide}>
        <div className={styles.detailRow}><b>Name</b><span>{mcp.name}</span></div>
        <div className={styles.detailRow}><b>Status</b>
          <span className={mcp.status === "online" ? styles.pillOnline : styles.pillOffline}>
            {mcp.status}
          </span>
        </div>
        <div className={styles.detailRow}><b>Kind</b><span>{mcp.kind}</span></div>
        <div className={styles.detailRow}><b>Version</b><span>{mcp.version || "-"}</span></div>
        <div className={styles.detailRow}><b>URL</b><span style={{ fontSize: 11 }}>{mcp.url}</span></div>
        {mcp.error && (
          <div className={styles.detailRow}><b>Fehler</b><span style={{ color: "var(--danger)" }}>{mcp.error}</span></div>
        )}
        <Link href="/debug/mcps" className={styles.mono} style={{ display: "block", marginTop: 12 }}>
          ← zur Liste
        </Link>
      </aside>
      <main className={styles.detailMain}>
        <h3 style={{ margin: "0 0 8px", fontSize: 13 }}>Beschreibung</h3>
        <p style={{ color: "var(--fg-secondary)", margin: "0 0 16px" }}>
          {mcp.description || "—"}
        </p>

        <h3 style={{ margin: "16px 0 8px", fontSize: 13 }}>Tools ({mcp.tools.length})</h3>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Kind</th>
              <th>Beschreibung</th>
            </tr>
          </thead>
          <tbody>
            {mcp.tools.length === 0 && (
              <tr><td colSpan={3} className={styles.empty}>—</td></tr>
            )}
            {mcp.tools.map((t) => (
              <tr key={t.name}>
                <td className={styles.mono}>{t.name}</td>
                <td>{t.kind || mcp.kind}</td>
                <td>{t.description || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 style={{ margin: "16px 0 8px", fontSize: 13 }}>Letzte Calls ({calls.length})</h3>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Zeit</th>
              <th>Trace</th>
              <th>Tool</th>
              <th>Daten</th>
            </tr>
          </thead>
          <tbody>
            {calls.length === 0 && (
              <tr><td colSpan={4} className={styles.empty}>Keine Calls geloggt.</td></tr>
            )}
            {calls.map((c, i) => {
              const data = (c.data ?? {}) as Record<string, unknown>;
              const toolName = (data.tool_name as string) || (data.role as string) || "";
              return (
                <tr key={`${c.trace_uid}-${c.sequence}-${i}`}>
                  <td className={styles.mono}>
                    {c.timestamp ? new Date(c.timestamp).toLocaleTimeString("de-DE") : "-"}
                  </td>
                  <td className={styles.mono}>
                    <Link href={`/debug/traces/${c.trace_uid}`}>{c.trace_uid.slice(0, 8)}</Link>
                  </td>
                  <td className={styles.mono}>{toolName}</td>
                  <td>
                    <pre style={{ margin: 0, fontSize: 11, maxHeight: 80, overflow: "auto" }}>
                      {JSON.stringify(data, null, 2)}
                    </pre>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </main>
    </div>
  );
}
