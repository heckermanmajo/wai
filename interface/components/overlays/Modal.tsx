"use client";

import { useEffect } from "react";
import styles from "./Modal.module.css";

interface Props {
  open: boolean;
  onClose: () => void;
  size?: "sm" | "md" | "lg" | "xl";
  children: React.ReactNode;
  // Wenn true wird der Inhalt nicht zentriert sondern fuellt Viewport (fuer Editor)
  fullscreen?: boolean;
}

const SIZE_MAP: Record<string, string> = {
  sm: "420px",
  md: "560px",
  lg: "780px",
  xl: "1100px",
};

export function Modal({ open, onClose, size = "md", fullscreen, children }: Props) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div
        className={styles.card}
        style={fullscreen ? undefined : { maxWidth: SIZE_MAP[size] }}
        data-fullscreen={fullscreen ? "1" : "0"}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
