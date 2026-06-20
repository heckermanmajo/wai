"use client";

import { useEffect } from "react";
import { ChatHeader } from "./ChatHeader";
import { Sidebar } from "./Sidebar";
import { MessageList } from "./MessageList";
import { InputArea } from "./InputArea";
import { ChatActions } from "./ChatActions";
import { ChatMappeView } from "./ChatMappeView";
import { DebugPanel } from "./DebugPanel";
import { Overlays } from "@/components/overlays/Overlays";
import { ErrorReporter } from "@/components/errors/ErrorReporter";
import { useChatStore } from "@/lib/store/useChatStore";
import { useUIStore } from "@/lib/store/useUIStore";
import { fetchChats } from "@/lib/api/chats";
import styles from "./ChatShell.module.css";

export function ChatShell({ slug }: { slug: string }) {
  const setChats = useChatStore((s) => s.setChats);
  const debugCollapsed = useUIStore((s) => s.debugCollapsed);
  const chatView = useUIStore((s) => s.chatView);
  const currentChatId = useChatStore((s) => s.currentChatId);

  useEffect(() => {
    fetchChats(slug)
      .then((r) => setChats(r.chats))
      .catch(() => {});
  }, [slug, setChats]);

  return (
    <div className={styles.app} data-debug-collapsed={debugCollapsed ? "1" : "0"}>
      <div className={styles.body}>
        <Sidebar slug={slug} />
        <main className={styles.main}>
          <ChatHeader />
          {currentChatId && chatView === "mappe" ? (
            <ChatMappeView slug={slug} />
          ) : (
            <>
              <MessageList slug={slug} />
              <ChatActions slug={slug} />
              <InputArea slug={slug} />
            </>
          )}
        </main>
        {!debugCollapsed && <DebugPanel />}
      </div>
      <Overlays slug={slug} />
      <ErrorReporter />
    </div>
  );
}
