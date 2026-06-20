"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useChatStore } from "@/lib/store/useChatStore";
import { useUIStore } from "@/lib/store/useUIStore";
import { fetchChatArtifacts, fetchChats, updateChat } from "@/lib/api/chats";
import styles from "./ChatHeader.module.css";

export function ChatHeader() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug ?? "";
  const chatId = useChatStore((s) => s.currentChatId);
  const chats = useChatStore((s) => s.chats);
  const setChats = useChatStore((s) => s.setChats);
  const artifacts = useChatStore((s) => (s.currentChatId ? s.artifactsByChat[s.currentChatId] : undefined));
  const setArtifacts = useChatStore((s) => s.setArtifacts);
  const streamingDone = useChatStore((s) => s.streaming?.isDone);
  const chatView = useUIStore((s) => s.chatView);
  const setChatView = useUIStore((s) => s.setChatView);
  const pushToast = useUIStore((s) => s.pushToast);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!chatId || !slug) return;
    fetchChatArtifacts(slug, chatId)
      .then((a) => setArtifacts(chatId, a))
      .catch(() => {});
  }, [slug, chatId, streamingDone, setArtifacts]);

  const chat = useMemo(() => chats.find((c) => c.id === chatId) ?? null, [chats, chatId]);
  const canEdit = !!chat && chat.is_mine;

  // Beim Chat-Wechsel den Edit-Modus verlassen
  useEffect(() => {
    setEditing(false);
  }, [chatId]);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const mappeCount = useMemo(() => {
    if (!artifacts) return 0;
    return (
      artifacts.documents.length +
      artifacts.crm_entities.length +
      artifacts.files.length +
      artifacts.tasks_notes_comments.tasks.length +
      artifacts.tasks_notes_comments.notes.length +
      artifacts.tasks_notes_comments.comments.length
    );
  }, [artifacts]);

  function startEdit() {
    if (!canEdit || !chat) return;
    setDraft(chat.title);
    setEditing(true);
  }

  async function commit() {
    if (!chat) return;
    const next = draft.trim();
    if (!next || next === chat.title) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await updateChat(slug, chat.id, { title: next });
      const r = await fetchChats(slug);
      setChats(r.chats);
      setEditing(false);
    } catch (e) {
      pushToast({ kind: "error", title: "Umbenennen fehlgeschlagen", body: String(e), ttlMs: 6000 });
    } finally {
      setSaving(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      void commit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      setEditing(false);
    }
  }

  return (
    <header className={styles.header}>
      <div className={styles.titleWrap}>
        {chat ? (
          <>
            {editing ? (
              <input
                ref={inputRef}
                className={styles.titleInput}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={() => void commit()}
                onKeyDown={onKeyDown}
                disabled={saving}
                maxLength={200}
              />
            ) : (
              <span
                className={`${styles.title} ${canEdit ? "" : styles.titleReadonly}`}
                onClick={startEdit}
                title={canEdit ? "Klicken zum Umbenennen" : undefined}
                role={canEdit ? "button" : undefined}
              >
                {chat.title}
              </span>
            )}
            <span className={styles.id}>#{chat.id}</span>
          </>
        ) : (
          <span className={styles.empty}>Keine Session aktiv</span>
        )}
      </div>
      {chat && (
        <nav className={styles.tabs}>
          <button
            className={styles.tabBtn}
            data-active={chatView === "chat" ? "1" : "0"}
            onClick={() => setChatView("chat")}
          >
            Chat
          </button>
          <button
            className={styles.tabBtn}
            data-active={chatView === "mappe" ? "1" : "0"}
            onClick={() => setChatView("mappe")}
          >
            Mappe
            {mappeCount > 0 && <span className={styles.count}>{mappeCount}</span>}
          </button>
        </nav>
      )}
    </header>
  );
}
