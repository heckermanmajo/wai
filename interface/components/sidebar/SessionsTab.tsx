"use client";

import { useEffect, useState } from "react";
import { useChatStore } from "@/lib/store/useChatStore";
import { cloneChat, createChat, deleteChat, fetchChats, shareChat } from "@/lib/api/chats";
import { useUIStore } from "@/lib/store/useUIStore";
import { ChatRowMenu, type ChatRowMenuAction } from "./ChatRowMenu";
import styles from "./Sidebar.module.css";

export function SessionsTab({ slug }: { slug: string }) {
  const chats = useChatStore((s) => s.chats);
  const setChats = useChatStore((s) => s.setChats);
  const currentId = useChatStore((s) => s.currentChatId);
  const setCurrentId = useChatStore((s) => s.setCurrentChatId);
  const pushToast = useUIStore((s) => s.pushToast);
  const [busy, setBusy] = useState(false);

  // Re-fetch nach neuer Message (streaming.isDone wechselt)
  const streamingDone = useChatStore((s) => s.streaming?.isDone);
  useEffect(() => {
    if (streamingDone === undefined) return;
    fetchChats(slug).then((r) => setChats(r.chats)).catch(() => {});
  }, [slug, streamingDone, setChats]);

  async function onNew() {
    setBusy(true);
    try {
      const c = await createChat(slug, "");
      const r = await fetchChats(slug);
      setChats(r.chats);
      setCurrentId(c.id);
    } finally {
      setBusy(false);
    }
  }

  async function onClone(id: number) {
    const c = await cloneChat(slug, id);
    const r = await fetchChats(slug);
    setChats(r.chats);
    setCurrentId(c.id);
    pushToast({ kind: "ok", title: "Chat geklont", ttlMs: 4000 });
  }

  async function onShare(id: number, shared: boolean) {
    await shareChat(slug, id, shared);
    const r = await fetchChats(slug);
    setChats(r.chats);
  }

  async function onArchive(id: number) {
    if (!confirm("Diesen Chat archivieren?")) return;
    await deleteChat(slug, id);
    const r = await fetchChats(slug);
    setChats(r.chats);
    if (currentId === id) setCurrentId(null);
  }

  return (
    <div className={styles.tab}>
      <button className={`primary ${styles.fullBtn}`} onClick={onNew} disabled={busy}>
        + Neuer Chat
      </button>
      <ul className={styles.list}>
        {chats.length === 0 && <li className={styles.empty}>Noch keine Sessions</li>}
        {chats.map((c) => {
          const menuActions: ChatRowMenuAction[] = [
            { key: "clone", label: "Klonen", icon: "⎘", onClick: () => onClone(c.id) },
          ];
          if (c.is_mine) {
            menuActions.push({
              key: "share",
              label: c.is_shared ? "Privat machen" : "Teilen",
              icon: c.is_shared ? "🔓" : "🔒",
              onClick: () => onShare(c.id, !c.is_shared),
            });
            menuActions.push({
              key: "archive",
              label: "Archivieren",
              icon: "🗑",
              danger: true,
              onClick: () => onArchive(c.id),
            });
          }
          return (
            <li
              key={c.id}
              className={styles.item}
              data-active={currentId === c.id ? "1" : "0"}
              onClick={() => setCurrentId(c.id)}
            >
              <div className={styles.row}>
                <div className={styles.title}>{c.title}</div>
                <div onClick={(e) => e.stopPropagation()}>
                  <ChatRowMenu actions={menuActions} />
                </div>
              </div>
              <div className={styles.meta}>
                <span className={styles.metaItem}>#{c.id}</span>
                {c.is_shared && <span className={styles.badge}>shared</span>}
                {!c.is_mine && <span className={styles.badge} data-kind="foreign">foreign</span>}
                {c.updated_at && (
                  <span className={styles.metaItem}>{new Date(c.updated_at).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })}</span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
