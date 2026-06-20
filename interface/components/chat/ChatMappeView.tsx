"use client";

import { useEffect } from "react";
import { useChatStore } from "@/lib/store/useChatStore";
import { useUIStore } from "@/lib/store/useUIStore";
import { fetchChatArtifacts } from "@/lib/api/chats";
import styles from "./ChatMappeView.module.css";

const ENTITY_LABEL: Record<string, string> = {
  "crm.contact": "Kontakt",
  "crm.account": "Account",
  "crm.lead": "Lead",
  "crm.deal": "Deal",
};

export function ChatMappeView({ slug }: { slug: string }) {
  const chatId = useChatStore((s) => s.currentChatId);
  const artifacts = useChatStore((s) => (s.currentChatId ? s.artifactsByChat[s.currentChatId] : undefined));
  const setArtifacts = useChatStore((s) => s.setArtifacts);
  const openEntity = useUIStore((s) => s.openEntity);
  const openDocument = useUIStore((s) => s.openDocument);
  const streamingDone = useChatStore((s) => s.streaming?.isDone);

  useEffect(() => {
    if (!chatId) return;
    fetchChatArtifacts(slug, chatId)
      .then((a) => setArtifacts(chatId, a))
      .catch(() => {});
  }, [slug, chatId, streamingDone, setArtifacts]);

  if (!chatId) return <div className={styles.empty}>Keine Session aktiv.</div>;
  if (!artifacts) return <div className={styles.empty}>Lade Mappe…</div>;

  const totals =
    artifacts.documents.length +
    artifacts.crm_entities.length +
    artifacts.files.length +
    artifacts.tool_calls.length +
    artifacts.tasks_notes_comments.tasks.length +
    artifacts.tasks_notes_comments.notes.length +
    artifacts.tasks_notes_comments.comments.length;

  if (totals === 0) {
    return (
      <div className={styles.wrap}>
        <div className={styles.empty}>
          Die Mappe ist leer. Alle Dokumente, Entitaeten, Dateien und Tool-Aufrufe
          dieses Chats erscheinen hier automatisch.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.inner}>
        {artifacts.documents.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>Dokumente</div>
            <div className={styles.grid}>
              {artifacts.documents.map((d) => (
                <button
                  key={d.id}
                  className={styles.card}
                  onClick={() => openDocument(d.id, chatId)}
                >
                  <strong>{d.title}</strong>
                  <span>v{d.version} · {d.author_display_name || ""}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {artifacts.crm_entities.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>CRM</div>
            <div className={styles.grid}>
              {artifacts.crm_entities.map((e) => {
                const cls = e.artifact_cls.replace("crm.", "");
                return (
                  <button
                    key={`${e.artifact_cls}-${e.artifact_id}`}
                    className={styles.card}
                    onClick={() => openEntity(cls, e.artifact_id)}
                  >
                    <strong>
                      {ENTITY_LABEL[e.artifact_cls] ?? e.artifact_cls} #{e.artifact_id}
                    </strong>
                    <span>{e.relation}</span>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {artifacts.files.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>Dateien</div>
            <div className={styles.grid}>
              {artifacts.files.map((f) => (
                <div key={f.id} className={styles.card}>
                  <strong>{f.filename || f.minio_key}</strong>
                  <span>{f.mime} · {Math.round(f.size_bytes / 1024)} KB</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {artifacts.tool_calls.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>Tool-Calls</div>
            <div className={styles.grid}>
              {artifacts.tool_calls.slice(0, 20).map((tc) => (
                <div key={tc.id} className={styles.card}>
                  <strong>{tc.tool_name}</strong>
                  <span data-status={tc.status}>
                    {tc.status} · {tc.duration_ms}ms
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {(artifacts.tasks_notes_comments.tasks.length > 0 ||
          artifacts.tasks_notes_comments.notes.length > 0 ||
          artifacts.tasks_notes_comments.comments.length > 0) && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>Notizen &amp; Tasks</div>
            <div className={styles.grid}>
              {artifacts.tasks_notes_comments.tasks.map((t) => (
                <div key={`task-${t.id}`} className={styles.card}>
                  <strong>Task: {t.title}</strong>
                  <span>{t.status}</span>
                </div>
              ))}
              {artifacts.tasks_notes_comments.notes.map((n) => (
                <div key={`note-${n.id}`} className={styles.card}>
                  <strong>{n.title || "Notiz"}</strong>
                  <span>{n.body.slice(0, 80)}</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
