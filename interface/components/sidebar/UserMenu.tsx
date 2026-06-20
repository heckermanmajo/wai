"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useMe } from "@/components/providers/MeProvider";
import { useUIStore } from "@/lib/store/useUIStore";
import { logout } from "@/lib/api/me";
import styles from "./UserMenu.module.css";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function UserMenu({ slug }: { slug: string }) {
  const me = useMe();
  const router = useRouter();
  const open = useUIStore((s) => s.userMenuOpen);
  const setOpen = useUIStore((s) => s.setUserMenuOpen);
  const toggleDebug = useUIStore((s) => s.toggleDebug);
  const debugCollapsed = useUIStore((s) => s.debugCollapsed);
  const errCount = useUIStore((s) => s.errors.length);
  const setErrorOpen = useUIStore((s) => s.setErrorOverlayOpen);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  async function onLogout() {
    setOpen(false);
    await logout(slug);
    router.replace("/login");
  }

  function onToggleDebug() {
    toggleDebug();
    setOpen(false);
  }

  function onShowErrors() {
    setErrorOpen(true);
    setOpen(false);
  }

  return (
    <div className={styles.wrap}>
      <button className={styles.trigger} onClick={() => setOpen(!open)} title="Menue">
        <span className={styles.avatar}>{initials(me.display_name)}</span>
        <span className={styles.userInfo}>
          <span className={styles.name}>{me.display_name}</span>
          <span className={styles.tenant}>{me.tenant_slug}</span>
        </span>
        {errCount > 0 && <span className={styles.errBadge}>{errCount}</span>}
        <span className={styles.gear}>⚙</span>
      </button>

      {open && (
        <>
          <div className={styles.backdrop} onClick={() => setOpen(false)} />
          <div className={styles.panel} role="menu">
            <div className={styles.section}>Workspace</div>
            <div className={styles.item} role="menuitem">
              <span>Tenant</span>
              <span className={styles.itemMeta}>{me.tenant_slug}</span>
            </div>
            <div className={styles.item} role="menuitem">
              <span>User</span>
              <span className={styles.itemMeta}>{me.username}</span>
            </div>

            <div className={styles.divider} />
            <div className={styles.section}>Tools</div>
            <button className={styles.item} onClick={onToggleDebug} role="menuitem">
              <span>{debugCollapsed ? "Debug-Panel anzeigen" : "Debug-Panel ausblenden"}</span>
            </button>
            <Link
              className={styles.item}
              href="/traces"
              onClick={() => setOpen(false)}
              role="menuitem"
            >
              <span>Traces</span>
              <span className={styles.itemMeta}>/traces</span>
            </Link>
            {errCount > 0 && (
              <button className={styles.item} onClick={onShowErrors} role="menuitem">
                <span>Fehler anzeigen</span>
                <span className={styles.itemMeta}>{errCount}</span>
              </button>
            )}

            <div className={styles.divider} />
            <button className={styles.item} data-danger="1" onClick={onLogout} role="menuitem">
              <span>Logout</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
