"use client";

import { useUIStore } from "@/lib/store/useUIStore";
import { Modal } from "./Modal";
import styles from "./ErrorOverlay.module.css";

export function ErrorOverlay() {
  const open = useUIStore((s) => s.errorOverlayOpen);
  const setOpen = useUIStore((s) => s.setErrorOverlayOpen);
  const errors = useUIStore((s) => s.errors);
  const clear = useUIStore((s) => s.clearErrors);

  return (
    <Modal open={open} onClose={() => setOpen(false)} size="lg">
      <header className={styles.header}>
        <strong>Frontend-Fehler ({errors.length})</strong>
        <div className={styles.actions}>
          <button onClick={clear}>Liste leeren</button>
          <button onClick={() => setOpen(false)} className={styles.close}>×</button>
        </div>
      </header>
      <div className={styles.body}>
        {errors.length === 0 && <div className={styles.empty}>Keine Fehler aufgezeichnet.</div>}
        {errors.map((e) => (
          <article key={e.id} className={styles.entry}>
            <div className={styles.row1}>
              <span className={styles.type}>{e.type}</span>
              <span className={styles.time}>{new Date(e.at).toLocaleTimeString()}</span>
            </div>
            <div className={styles.message}>{e.message}</div>
            {e.url && <div className={styles.url}>{e.url}</div>}
            {e.stack && <pre className={styles.stack}>{e.stack}</pre>}
          </article>
        ))}
      </div>
    </Modal>
  );
}
