"use client";

import { useChatStore } from "@/lib/store/useChatStore";
import styles from "./StatusPill.module.css";

export function StatusPill() {
  const stream = useChatStore((s) => s.streaming);
  if (!stream) return null;
  const done = stream.isDone;
  return (
    <div className={styles.pill} data-done={done ? "1" : "0"}>
      {!done && <span className={styles.spinner} />}
      <span className={styles.text}>{stream.statusText}</span>
      {stream.statusSub && <span className={styles.sub}>{stream.statusSub}</span>}
    </div>
  );
}
