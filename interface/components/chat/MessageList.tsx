"use client";

import { useEffect, useRef } from "react";
import { useChatStore } from "@/lib/store/useChatStore";
import { MessageBubble } from "./MessageBubble";
import { StreamingBubble } from "./StreamingBubble";
import { StatusPill } from "./StatusPill";
import { fetchChat } from "@/lib/api/chats";
import type { MessageDto } from "@/lib/api/types";
import styles from "./MessageList.module.css";

// Stabile leere Referenz — Zustand-Selector darf KEIN frisches `[]` zurueckgeben,
// sonst loest useSyncExternalStore "result of getSnapshot should be cached" aus
// und gerät in eine Render-Schleife.
const EMPTY: MessageDto[] = [];

export function MessageList({ slug }: { slug: string }) {
  const chatId = useChatStore((s) => s.currentChatId);
  const messages = useChatStore((s) =>
    s.currentChatId ? s.messagesByChat[s.currentChatId] ?? EMPTY : EMPTY,
  );
  const setMessages = useChatStore((s) => s.setMessages);
  const streaming = useChatStore((s) => s.streaming);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Beim Chat-Wechsel: Detail nachladen wenn nicht im Cache
  useEffect(() => {
    if (!chatId) return;
    fetchChat(slug, chatId)
      .then((r) => setMessages(chatId, r.messages))
      .catch(() => {});
  }, [slug, chatId, setMessages]);

  // Auto-Scroll an Ende bei neuen Messages oder Stream
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, streaming?.statusText, streaming?.isDone]);

  if (!chatId) {
    return (
      <div className={styles.empty}>
        <p>Waehle links eine Session oder erstelle eine neue.</p>
      </div>
    );
  }

  return (
    <div className={styles.scroll} ref={scrollRef}>
      <div className={styles.list}>
        {messages.map((m) => (
          <MessageBubble key={m.id} msg={m} />
        ))}
        {streaming && streaming.chatId === chatId && (
          <>
            <StatusPill />
            {!streaming.isDone && <StreamingBubble />}
          </>
        )}
      </div>
    </div>
  );
}
