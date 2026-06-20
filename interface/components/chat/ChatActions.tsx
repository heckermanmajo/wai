"use client";

import { useEffect, useMemo, useState } from "react";
import { useChatStore } from "@/lib/store/useChatStore";
import { useUIStore } from "@/lib/store/useUIStore";
import { useChatStream } from "@/lib/sse/useChatStream";
import { listActions, runAction } from "@/lib/api/actions";
import { fetchChats } from "@/lib/api/chats";
import type { ActionDto } from "@/lib/api/types";
import styles from "./ChatActions.module.css";

export function ChatActions({ slug }: { slug: string }) {
  const currentChatId = useChatStore((s) => s.currentChatId);
  const setCurrentChatId = useChatStore((s) => s.setCurrentChatId);
  const setChats = useChatStore((s) => s.setChats);
  const streaming = useChatStore((s) => s.streaming);
  const pushToast = useUIStore((s) => s.pushToast);
  const { send } = useChatStream(slug);

  const [global, setGlobal] = useState<ActionDto[]>([]);
  const [chatActions, setChatActions] = useState<ActionDto[]>([]);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const disabled = !!streaming && !streaming.isDone;

  useEffect(() => {
    listActions(slug, { limit: 8 })
      .then((r) => setGlobal(r.actions))
      .catch(() => setGlobal([]));
  }, [slug]);

  useEffect(() => {
    if (!currentChatId) {
      setChatActions([]);
      return;
    }
    listActions(slug, { cls: "ai.chat", id: currentChatId, limit: 4 })
      .then((r) => setChatActions(r.actions))
      .catch(() => setChatActions([]));
  }, [slug, currentChatId]);

  const visible = useMemo(() => {
    // Chat-spezifische zuerst, dann globale; doppelte Keys filtern
    const seen = new Set<string>();
    const out: ActionDto[] = [];
    for (const a of [...chatActions, ...global]) {
      if (seen.has(a.key)) continue;
      seen.add(a.key);
      out.push(a);
    }
    return out.slice(0, 10);
  }, [chatActions, global]);

  async function onRun(action: ActionDto) {
    if (disabled || busyKey) return;
    setBusyKey(action.key);
    try {
      const body: { action_key: string; cls?: string; id?: number; chat_id?: number } = {
        action_key: action.key,
      };
      if (currentChatId) body.chat_id = currentChatId;
      // chat.* Aktionen brauchen die Resource-Referenz
      if (action.resource_types.includes("ai.chat") && currentChatId) {
        body.cls = "ai.chat";
        body.id = currentChatId;
      }
      const r = await runAction(slug, body);
      if (r.kind === "chat_task") {
        // Falls Backend einen neuen Chat angelegt hat -> uebernehmen
        if (!currentChatId || r.chat_id !== currentChatId) {
          setCurrentChatId(r.chat_id);
          // Sidebar refreshen, neuer Chat soll auftauchen
          fetchChats(slug).then((res) => setChats(res.chats)).catch(() => {});
        }
        await send(r.chat_id, r.prompt);
      } else {
        pushToast({
          kind: "ok",
          title: `${action.label}: ${r.tool}`,
          body: JSON.stringify(r.result).slice(0, 200),
          ttlMs: 6000,
        });
      }
    } catch (e) {
      pushToast({
        kind: "error",
        title: `${action.label} fehlgeschlagen`,
        body: String(e),
        ttlMs: 8000,
      });
    } finally {
      setBusyKey(null);
    }
  }

  if (visible.length === 0) return null;

  return (
    <div className={styles.bar} role="toolbar" aria-label="Aktionen">
      <span className={styles.label}>Aktionen</span>
      {visible.map((a) => (
        <button
          key={a.key}
          className={styles.chip}
          onClick={() => onRun(a)}
          disabled={disabled || busyKey === a.key}
          title={a.description}
        >
          {a.icon && <span className={styles.icon}>{a.icon}</span>}
          <span>{a.label}</span>
        </button>
      ))}
    </div>
  );
}
