"use client";

import { useEffect, useMemo, useState } from "react";
import { useUIStore } from "@/lib/store/useUIStore";
import { useDocStore } from "@/lib/store/useDocStore";
import { createDocument, listDocuments } from "@/lib/api/documents";
import styles from "./Sidebar.module.css";

export function DocumentsTab({ slug }: { slug: string }) {
  const allDocs = useDocStore((s) => s.allDocs);
  const setAllDocs = useDocStore((s) => s.setAllDocs);
  const search = useDocStore((s) => s.searchFilter);
  const setSearch = useDocStore((s) => s.setSearchFilter);
  const openDoc = useUIStore((s) => s.openDocument);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listDocuments(slug).then((r) => setAllDocs(r.documents)).catch(() => {});
  }, [slug, setAllDocs]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return allDocs;
    return allDocs.filter(
      (d) =>
        d.title.toLowerCase().includes(q) ||
        d.author_display_name?.toLowerCase().includes(q),
    );
  }, [allDocs, search]);

  async function onNew() {
    setBusy(true);
    try {
      const d = await createDocument(slug, {});
      const r = await listDocuments(slug);
      setAllDocs(r.documents);
      openDoc(d.id);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.tab}>
      <button className={`primary ${styles.fullBtn}`} onClick={onNew} disabled={busy}>
        + Neues Dokument
      </button>
      <input
        type="search"
        placeholder="Suchen…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className={styles.search}
      />
      <ul className={styles.list}>
        {filtered.length === 0 && <li className={styles.empty}>Keine Dokumente</li>}
        {filtered.map((d) => (
          <li
            key={d.id}
            className={styles.item}
            onClick={() => openDoc(d.id)}
          >
            <div className={styles.title}>{d.title}</div>
            <div className={styles.meta}>
              <span className={styles.metaItem}>v{d.version}</span>
              <span className={styles.metaItem}>{d.author_display_name}</span>
              {d.updated_at && (
                <span className={styles.metaItem}>
                  {new Date(d.updated_at).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
