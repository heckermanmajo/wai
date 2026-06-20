"use client";

import { useSyncExternalStore } from "react";
import { streamBus } from "@/lib/sse/streamBus";
import { MarkdownView } from "@/components/markdown/MarkdownView";
import styles from "./MessageBubble.module.css";
import bubbleStyles from "./StreamingBubble.module.css";

// Subscribed via useSyncExternalStore — re-rendert NUR diese Bubble bei jedem
// llm_delta. MessageList bleibt stabil. Snapshot ist identitaets-stabil, solange
// kein neuer Delta kommt (siehe streamBus.cachedSnapshot).
export function StreamingBubble() {
  const snap = useSyncExternalStore(
    streamBus.subscribe,
    streamBus.getSnapshot,
    streamBus.getSnapshot, // SSR-Snapshot = client-Snapshot (kein hydration mismatch, weil Bubble client-only mounted)
  );
  return (
    <div className={styles.msg} data-role="assistant">
      <div className={styles.role}>wai</div>
      <div className={styles.body}>
        {snap.text ? <MarkdownView content={snap.text} streaming /> : <em className={bubbleStyles.placeholder}>…</em>}
        {snap.caret && <span className={bubbleStyles.caret} />}
      </div>
    </div>
  );
}
