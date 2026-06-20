"use client";

import { useEffect, useState } from "react";
import { useUIStore } from "@/lib/store/useUIStore";
import { diffVersion } from "@/lib/api/documents";
import type { DocumentDiff } from "@/lib/api/types";
import { Modal } from "./Modal";
import styles from "./DiffOverlay.module.css";

export function DiffOverlay({ slug }: { slug: string }) {
  const ovl = useUIStore((s) => s.diffOverlay);
  const close = useUIStore((s) => s.closeDiff);
  const [diff, setDiff] = useState<DocumentDiff | null>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    if (!ovl) {
      setDiff(null);
      setErr("");
      return;
    }
    setDiff(null);
    setErr("");
    diffVersion(slug, ovl.docId, ovl.versionId, ovl.against)
      .then(setDiff)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [slug, ovl]);

  return (
    <Modal open={!!ovl} onClose={close} size="xl">
      <header className={styles.header}>
        <strong>Diff</strong>
        {diff && (
          <span className={styles.labels}>
            <span className={styles.from}>{diff.from.label}</span>
            <span>→</span>
            <span className={styles.to}>{diff.to.label}</span>
          </span>
        )}
        <button onClick={close} className={styles.close}>×</button>
      </header>
      <div className={styles.body}>
        {err && <div className={styles.err}>{err}</div>}
        {!diff && !err && <div className={styles.loading}>Laedt…</div>}
        {diff && (
          <pre className={styles.diff}>
            {diff.content_diff.map((seg, idx) => {
              const key = `${idx}-${seg.kind}`;
              if (seg.kind === "equal") {
                return (
                  <span key={key} className={styles.equal}>
                    {seg.old_text}
                    {seg.old_text && !seg.old_text.endsWith("\n") ? "\n" : ""}
                  </span>
                );
              }
              return (
                <span key={key}>
                  {seg.old_text && (
                    <span className={styles.del}>{`- ${seg.old_text.replace(/\n/g, "\n- ")}\n`}</span>
                  )}
                  {seg.new_text && (
                    <span className={styles.ins}>{`+ ${seg.new_text.replace(/\n/g, "\n+ ")}\n`}</span>
                  )}
                </span>
              );
            })}
          </pre>
        )}
      </div>
    </Modal>
  );
}
