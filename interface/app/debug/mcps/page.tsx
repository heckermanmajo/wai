"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchDebugMcps, type DebugMcpEntry } from "@/lib/api/debug";
import styles from "../debug.module.css";

export default function DebugMcpsPage() {
  const [items, setItems] = useState<DebugMcpEntry[] | null>(null);
  const [err, setErr] = useState<string>("");

  function reload() {
    setErr("");
    fetchDebugMcps()
      .then((r) => setItems(r.mcps))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }

  useEffect(reload, []);

  const tools = items?.filter((m) => m.kind === "tool") ?? [];
  const subAgents = items?.filter((m) => m.kind === "sub_agent") ?? [];
  const mixed = items?.filter((m) => m.kind === "mixed") ?? [];
  const unknown = items?.filter(
    (m) => !["tool", "sub_agent", "mixed"].includes(m.kind),
  ) ?? [];

  return (
    <div className={styles.content}>
      <div className={styles.toolbar}>
        <button onClick={reload}>Reload</button>
        <span className={styles.mono} style={{ marginLeft: "auto" }}>
          {items?.length ?? 0} MCPs
        </span>
      </div>
      {err && <div className={styles.error}>{err}</div>}
      <div className={styles.list}>
        <Section title="MCPs (passiv, kind=tool)" items={tools} />
        <Section title="Sub-Agent-Rollen (kind=sub_agent)" items={subAgents} />
        {mixed.length > 0 && <Section title="Mixed" items={mixed} />}
        {unknown.length > 0 && <Section title="Status unbekannt" items={unknown} />}
      </div>
    </div>
  );
}

function Section({ title, items }: { title: string; items: DebugMcpEntry[] }) {
  if (items.length === 0) return null;
  return (
    <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border-subtle)" }}>
      <h3 style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--fg-secondary)", margin: "0 0 8px" }}>
        {title}
      </h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Version</th>
            <th>Tools</th>
            <th>Endpoint</th>
            <th>Beschreibung</th>
          </tr>
        </thead>
        <tbody>
          {items.map((m) => (
            <tr key={m.name}>
              <td className={styles.mono}>
                <Link href={`/debug/mcps/${m.name}`}>{m.name}</Link>
              </td>
              <td>
                <span className={m.status === "online" ? styles.pillOnline : styles.pillOffline}>
                  {m.status}
                </span>
              </td>
              <td className={styles.mono}>{m.version || "-"}</td>
              <td className={styles.mono}>{m.tools.length}</td>
              <td className={styles.mono} style={{ fontSize: 11 }}>{m.url}</td>
              <td>{m.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
