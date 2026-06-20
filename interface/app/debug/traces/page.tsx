"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { fetchDebugMe, fetchDebugTraces, type DebugMe } from "@/lib/api/debug";
import type { TraceRow } from "@/lib/api/types";
import styles from "../debug.module.css";

export default function DebugTracesPage() {
  const [rows, setRows] = useState<TraceRow[]>([]);
  const [me, setMe] = useState<DebugMe | null>(null);
  const [tenantId, setTenantId] = useState("");
  const [status, setStatus] = useState("");
  const [intent, setIntent] = useState("");
  const [minDuration, setMinDuration] = useState("");
  const [maxDuration, setMaxDuration] = useState("");
  const [limit, setLimit] = useState(100);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    fetchDebugMe().then(setMe).catch(() => {});
  }, []);

  const reload = useCallback(() => {
    setErr("");
    fetchDebugTraces({
      tenant_id: tenantId.trim() || undefined,
      status: status || undefined,
      intent: intent.trim() || undefined,
      min_duration: minDuration ? Number(minDuration) : undefined,
      max_duration: maxDuration ? Number(maxDuration) : undefined,
      limit,
    })
      .then((r) => setRows(r.traces))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [tenantId, status, intent, minDuration, maxDuration, limit]);

  useEffect(() => reload(), [reload]);

  const tenantOptions = me?.platform_role === "admin" ? null : me?.memberships ?? [];

  return (
    <div className={styles.content}>
      <div className={styles.toolbar}>
        {tenantOptions ? (
          <select value={tenantId} onChange={(e) => setTenantId(e.target.value)}>
            <option value="">alle (eigene Tenants)</option>
            {tenantOptions.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        ) : (
          <input
            placeholder="tenant_id (leer = alle)"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
          />
        )}
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">alle Status</option>
          <option value="ok">ok</option>
          <option value="error">error</option>
          <option value="running">running</option>
        </select>
        <input
          placeholder="intent"
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          style={{ width: 120 }}
        />
        <input
          placeholder="min ms"
          value={minDuration}
          onChange={(e) => setMinDuration(e.target.value.replace(/\D/g, ""))}
          style={{ width: 70 }}
        />
        <input
          placeholder="max ms"
          value={maxDuration}
          onChange={(e) => setMaxDuration(e.target.value.replace(/\D/g, ""))}
          style={{ width: 70 }}
        />
        <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
          {[25, 50, 100, 250, 500].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
        <button onClick={reload}>Reload</button>
        <span className={styles.mono} style={{ marginLeft: "auto" }}>{rows.length} Traces</span>
      </div>
      {err && <div className={styles.error}>{err}</div>}
      <div className={styles.list}>
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
            {rows.length === 0 && !err && (
              <tr><td colSpan={9} className={styles.empty}>Keine Traces</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.trace_uid}>
                <td className={styles.mono}>
                  {r.started_at
                    ? new Date(r.started_at).toLocaleTimeString("de-DE")
                    : "-"}
                </td>
                <td className={styles.mono}>
                  <Link href={`/debug/traces/${r.trace_uid}`}>
                    {r.trace_uid.slice(0, 8)}
                  </Link>
                </td>
                <td>{r.tenant_id}</td>
                <td>
                  <span
                    className={
                      r.status === "ok"
                        ? styles.pillOk
                        : r.status === "error"
                        ? styles.pillError
                        : styles.pillRunning
                    }
                  >
                    {r.status}
                  </span>
                </td>
                <td>{r.intent || "-"}</td>
                <td className={styles.mono}>{r.duration_ms}</td>
                <td className={styles.mono}>{r.tool_call_count}</td>
                <td className={styles.mono}>{r.event_count}</td>
                <td style={{ maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {r.user_message}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
