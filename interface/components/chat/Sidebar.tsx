"use client";

import { useUIStore, type SidebarTab } from "@/lib/store/useUIStore";
import { SessionsTab } from "@/components/sidebar/SessionsTab";
import { DocumentsTab } from "@/components/sidebar/DocumentsTab";
import { UserMenu } from "@/components/sidebar/UserMenu";
import styles from "./Sidebar.module.css";

const TABS: { id: SidebarTab; label: string }[] = [
  { id: "sessions", label: "Sessions" },
  { id: "documents", label: "Dokumente" },
];

export function Sidebar({ slug }: { slug: string }) {
  const tab = useUIStore((s) => s.sidebarTab);
  const setTab = useUIStore((s) => s.setSidebarTab);
  // Migration: alter persistierter Wert "mappe" existiert nicht mehr.
  const effectiveTab = tab === "sessions" || tab === "documents" ? tab : "sessions";

  return (
    <aside className={styles.sidebar}>
      <nav className={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t.id}
            className={styles.tabBtn}
            data-active={effectiveTab === t.id ? "1" : "0"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className={styles.body}>
        {effectiveTab === "sessions" && <SessionsTab slug={slug} />}
        {effectiveTab === "documents" && <DocumentsTab slug={slug} />}
      </div>
      <UserMenu slug={slug} />
    </aside>
  );
}
