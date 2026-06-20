"use client";

import { useEffect, useState } from "react";
import {
  fetchEntityChanges,
  type EntityChange,
  type FieldDiff,
} from "@/lib/api/changes";
import styles from "./EntityOverlay.module.css";

function formatTs(iso: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function actorLabel(c: EntityChange): string {
  if (c.actor_type === "ai") {
    return `AI (${c.agent_name || "agent"})`;
  }
  if (c.actor_type === "system") {
    return "System";
  }
  return `User #${c.actor_id || "?"}`;
}

function actorIcon(c: EntityChange): string {
  if (c.actor_type === "ai") return "[AI]";
  if (c.actor_type === "system") return "[SYS]";
  return "[USR]";
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function FieldDiffRow({ d }: { d: FieldDiff }) {
  if (d.truncated) {
    return (
      <tr>
        <th>{d.field}</th>
        <td colSpan={2} className={styles.changeTruncated}>
          Inhalt geaendert ({Math.round((d.old_len ?? 0) / 1024)} kB → {Math.round((d.new_len ?? 0) / 1024)} kB)
        </td>
      </tr>
    );
  }
  return (
    <tr>
      <th>{d.field}</th>
      <td className={styles.changeOld}>{formatValue(d.old)}</td>
      <td className={styles.changeNew}>{formatValue(d.new)}</td>
    </tr>
  );
}

function ChangeCard({ c }: { c: EntityChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={styles.changeCard}>
      <button
        type="button"
        className={styles.changeHeader}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={styles.changeTs}>{formatTs(c.created_at)}</span>
        <span className={styles.changeActor}>{actorIcon(c)} {actorLabel(c)}</span>
        <span className={styles.changeType}>{c.change_type}</span>
        <span className={styles.changeSummary}>{c.summary || "—"}</span>
        <span className={styles.changeToggle}>{open ? "▾" : "▸"}</span>
      </button>
      {open && c.field_diffs.length > 0 && (
        <table className={styles.changeTable}>
          <thead>
            <tr>
              <th>Feld</th>
              <th>Vorher</th>
              <th>Nachher</th>
            </tr>
          </thead>
          <tbody>
            {c.field_diffs.map((d, i) => (
              <FieldDiffRow key={`${d.field}-${i}`} d={d} />
            ))}
          </tbody>
        </table>
      )}
      {open && c.trace_uid && (
        <a
          className={styles.changeTraceLink}
          href={`/traces#${c.trace_uid}`}
          target="_blank"
          rel="noreferrer"
        >
          → Trace anzeigen
        </a>
      )}
    </div>
  );
}

export function EntityChangesTab({
  slug,
  cls,
  id,
}: {
  slug: string;
  cls: string;
  id: number;
}) {
  const [items, setItems] = useState<EntityChange[] | null>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    setItems(null);
    setErr("");
    fetchEntityChanges(slug, cls, id, { limit: 50 })
      .then((r) => setItems(r.changes))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [slug, cls, id]);

  if (err) return <div className={styles.err}>{err}</div>;
  if (!items) return <div className={styles.loading}>Laedt…</div>;
  if (items.length === 0) {
    return <div className={styles.loading}>Keine Aenderungen erfasst.</div>;
  }
  return (
    <div className={styles.changeList}>
      {items.map((c) => (
        <ChangeCard key={c.id} c={c} />
      ))}
    </div>
  );
}
