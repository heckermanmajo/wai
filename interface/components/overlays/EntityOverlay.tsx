"use client";

import { useEffect, useState } from "react";
import { useUIStore } from "@/lib/store/useUIStore";
import { fetchEntity } from "@/lib/api/entities";
import type { EntityCls } from "@/lib/api/types";
import { Modal } from "./Modal";
import { EntityChangesTab } from "./EntityChangesTab";
import styles from "./EntityOverlay.module.css";

type Tab = "detail" | "changes";

export function EntityOverlay({ slug }: { slug: string }) {
  const ovl = useUIStore((s) => s.entityOverlay);
  const close = useUIStore((s) => s.closeEntity);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string>("");
  const [tab, setTab] = useState<Tab>("detail");

  useEffect(() => {
    if (!ovl) {
      setData(null);
      setErr("");
      setTab("detail");
      return;
    }
    setData(null);
    setErr("");
    setTab("detail");
    fetchEntity(slug, ovl.cls as EntityCls, ovl.id)
      .then((r) => setData(r.data))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [slug, ovl]);

  return (
    <Modal open={!!ovl} onClose={close} size="md">
      <header className={styles.header}>
        <strong>{ovl?.cls} #{ovl?.id}</strong>
        {ovl?.label && <span className={styles.label}>{ovl.label}</span>}
        <button onClick={close} className={styles.close}>×</button>
      </header>
      <nav className={styles.tabs}>
        <button
          type="button"
          className={tab === "detail" ? styles.tabActive : styles.tab}
          onClick={() => setTab("detail")}
        >
          Detail
        </button>
        <button
          type="button"
          className={tab === "changes" ? styles.tabActive : styles.tab}
          onClick={() => setTab("changes")}
        >
          Verlauf
        </button>
      </nav>
      <div className={styles.body}>
        {tab === "detail" && (
          <>
            {err && <div className={styles.err}>{err}</div>}
            {!data && !err && <div className={styles.loading}>Laedt…</div>}
            {data && (
              <table className={styles.table}>
                <tbody>
                  {Object.entries(data).map(([k, v]) => (
                    <tr key={k}>
                      <th>{k}</th>
                      <td>{typeof v === "object" ? <pre>{JSON.stringify(v, null, 2)}</pre> : String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
        {tab === "changes" && ovl && (
          <EntityChangesTab slug={slug} cls={ovl.cls} id={ovl.id} />
        )}
      </div>
    </Modal>
  );
}
