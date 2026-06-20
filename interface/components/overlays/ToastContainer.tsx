"use client";

import { useUIStore } from "@/lib/store/useUIStore";
import styles from "./ToastContainer.module.css";

export function ToastContainer() {
  const toasts = useUIStore((s) => s.toasts);
  const dismiss = useUIStore((s) => s.dismissToast);

  return (
    <div className={styles.stack}>
      {toasts.map((t) => (
        <div key={t.id} className={styles.toast} data-kind={t.kind} onClick={() => dismiss(t.id)}>
          <strong>{t.title}</strong>
          {t.body && <div className={styles.body}>{t.body}</div>}
        </div>
      ))}
    </div>
  );
}
