"use client";

import { useEffect, useRef, useState } from "react";
import { useDocStore } from "@/lib/store/useDocStore";
import { useUIStore } from "@/lib/store/useUIStore";
import {
  deleteDocument,
  getDocument,
  getVersion,
  listVersions,
  restoreVersion,
  updateDocument,
} from "@/lib/api/documents";
import type { DocumentVersionListItem } from "@/lib/api/types";
import { Modal } from "./Modal";
import { MarkdownView } from "@/components/markdown/MarkdownView";
import styles from "./DocumentOverlay.module.css";

export function DocumentOverlay({ slug }: { slug: string }) {
  const ovl = useUIStore((s) => s.documentOverlay);
  const close = useUIStore((s) => s.closeDocument);
  const openDiff = useUIStore((s) => s.openDiff);
  const pushToast = useUIStore((s) => s.pushToast);
  const current = useDocStore((s) => s.current);
  const setCurrent = useDocStore((s) => s.setCurrent);
  const dirty = useDocStore((s) => s.dirty);
  const setDirty = useDocStore((s) => s.setDirty);
  const viewingVersionId = useDocStore((s) => s.viewingVersionId);
  const setViewingVersionId = useDocStore((s) => s.setViewingVersionId);
  const viewingVersion = useDocStore((s) => s.viewingVersion);
  const setViewingVersion = useDocStore((s) => s.setViewingVersion);
  const autosaveOn = useDocStore((s) => s.autosaveOn);
  const setAutosaveOn = useDocStore((s) => s.setAutosaveOn);

  const [versions, setVersions] = useState<DocumentVersionListItem[]>([]);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [preview, setPreview] = useState(false);
  const autosaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Initial load
  useEffect(() => {
    if (!ovl) {
      setCurrent(null);
      setVersions([]);
      setViewingVersionId(null);
      setViewingVersion(null);
      return;
    }
    getDocument(slug, ovl.docId).then((d) => {
      setCurrent(d);
      setEditTitle(d.title);
      setEditContent(d.content);
    });
    listVersions(slug, ovl.docId).then((r) => setVersions(r.versions));
  }, [slug, ovl, setCurrent, setViewingVersionId, setViewingVersion]);

  // Specific version load
  useEffect(() => {
    if (!ovl || viewingVersionId === null) {
      setViewingVersion(null);
      return;
    }
    getVersion(slug, ovl.docId, viewingVersionId).then(setViewingVersion);
  }, [slug, ovl, viewingVersionId, setViewingVersion]);

  function onChange(t: string, c: string) {
    setEditTitle(t);
    setEditContent(c);
    setDirty(t !== current?.title || c !== current?.content);
    if (autosaveOn && current) {
      if (autosaveRef.current) clearTimeout(autosaveRef.current);
      autosaveRef.current = setTimeout(() => void onSave(), 1500);
    }
  }

  async function onSave() {
    if (!current) return;
    const d = await updateDocument(slug, current.id, { title: editTitle, content: editContent });
    setCurrent(d);
    setEditTitle(d.title);
    setEditContent(d.content);
    setDirty(false);
    if (ovl) {
      const r = await listVersions(slug, ovl.docId);
      setVersions(r.versions);
    }
    pushToast({ kind: "ok", title: "Gespeichert", body: `v${d.version}`, ttlMs: 4000 });
  }

  async function onDelete() {
    if (!current) return;
    if (!confirm("Dokument loeschen?")) return;
    await deleteDocument(slug, current.id);
    pushToast({ kind: "ok", title: "Geloescht", ttlMs: 4000 });
    close();
  }

  async function onRestore() {
    if (!current || viewingVersionId === null) return;
    const d = await restoreVersion(slug, current.id, viewingVersionId);
    setCurrent(d);
    setEditTitle(d.title);
    setEditContent(d.content);
    setViewingVersionId(null);
    if (ovl) {
      const r = await listVersions(slug, ovl.docId);
      setVersions(r.versions);
    }
    pushToast({ kind: "ok", title: "Wiederhergestellt", body: `Neue v${d.version}`, ttlMs: 4000 });
  }

  return (
    <Modal open={!!ovl} onClose={close} fullscreen>
      <header className={styles.header}>
        {viewingVersionId === null ? (
          <input
            className={styles.title}
            value={editTitle}
            onChange={(e) => onChange(e.target.value, editContent)}
            placeholder="Titel…"
          />
        ) : (
          <span className={styles.title}>{viewingVersion?.title ?? "…"} <em>(v{viewingVersion?.version})</em></span>
        )}
        <div className={styles.actions}>
          <button onClick={() => setPreview((p) => !p)}>{preview ? "Editor" : "Preview"}</button>
          <label className={styles.autosave}>
            <input
              type="checkbox"
              checked={autosaveOn}
              onChange={(e) => setAutosaveOn(e.target.checked)}
            />{" "}
            Autosave
          </label>
          {viewingVersionId !== null ? (
            <button className="primary" onClick={onRestore}>Wiederherstellen</button>
          ) : (
            <button className="primary" onClick={onSave} disabled={!dirty}>Speichern</button>
          )}
          {viewingVersionId === null && <button onClick={onDelete}>Loeschen</button>}
          <button onClick={close} className={styles.close}>×</button>
        </div>
      </header>
      <div className={styles.grid}>
        <div className={styles.editor}>
          {viewingVersionId === null ? (
            preview ? (
              <MarkdownView content={editContent} className={styles.preview} />
            ) : (
              <textarea
                className={styles.textarea}
                value={editContent}
                onChange={(e) => onChange(editTitle, e.target.value)}
                placeholder="Markdown…"
              />
            )
          ) : (
            <MarkdownView content={viewingVersion?.content ?? ""} className={styles.preview} />
          )}
        </div>
        <aside className={styles.versions}>
          <div className={styles.versionsHead}>
            Versionen
            <button onClick={() => setViewingVersionId(null)} disabled={viewingVersionId === null}>
              Aktuelle
            </button>
          </div>
          <ul>
            {versions.map((v) => (
              <li
                key={v.id}
                className={styles.verItem}
                data-active={viewingVersionId === v.id ? "1" : "0"}
              >
                <div onClick={() => setViewingVersionId(v.id)} className={styles.verLink}>
                  <strong>v{v.version}</strong>
                  <span>{v.author_display_name}</span>
                  <span>{v.content_length} Zeichen</span>
                  {v.created_at && (
                    <span>{new Date(v.created_at).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })}</span>
                  )}
                </div>
                <button
                  className={styles.diffBtn}
                  onClick={() => current && openDiff(current.id, v.id, "current")}
                  title="Diff gegen aktuelle Version"
                >
                  Δ
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </Modal>
  );
}
