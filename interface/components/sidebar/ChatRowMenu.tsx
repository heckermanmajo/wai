"use client";

import { useEffect, useState } from "react";
import styles from "./ChatRowMenu.module.css";

export interface ChatRowMenuAction {
  key: string;
  label: string;
  icon?: string;
  onClick: () => void;
  danger?: boolean;
}

export function ChatRowMenu({ actions }: { actions: ChatRowMenuAction[] }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.trigger}
        data-open={open ? "1" : "0"}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        title="Optionen"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        ⋯
      </button>
      {open && (
        <>
          <div className={styles.backdrop} onClick={() => setOpen(false)} />
          <div className={styles.menu} role="menu" onClick={(e) => e.stopPropagation()}>
            {actions.map((a) => (
              <button
                key={a.key}
                type="button"
                className={styles.item}
                data-danger={a.danger ? "1" : "0"}
                onClick={() => {
                  setOpen(false);
                  a.onClick();
                }}
                role="menuitem"
              >
                {a.icon && <span className={styles.icon}>{a.icon}</span>}
                <span>{a.label}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
