"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchDebugMe, type DebugMe } from "@/lib/api/debug";
import styles from "./debug.module.css";

const TABS: { href: string; label: string }[] = [
  { href: "/debug/live", label: "Live" },
  { href: "/debug/traces", label: "Traces" },
  { href: "/debug/mcps", label: "MCPs & Agents" },
];

export default function DebugLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [me, setMe] = useState<DebugMe | null>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    fetchDebugMe()
      .then(setMe)
      .catch((e) => {
        const status = (e as { status?: number } | null)?.status;
        if (status === 401) {
          setErr("Bitte einloggen.");
        } else if (status === 403) {
          setErr("Kein Debug-View-Zugriff (platform_role muss admin oder supporter sein).");
        } else {
          setErr(e instanceof Error ? e.message : String(e));
        }
      });
  }, []);

  if (err) {
    return (
      <div className={styles.shell}>
        <div className={styles.gate}>{err}</div>
      </div>
    );
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <strong className={styles.brand}>wai · Debug</strong>
        <nav className={styles.tabs}>
          {TABS.map((t) => {
            const active = pathname?.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={active ? styles.tabActive : styles.tab}
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
        <div className={styles.userBox}>
          {me ? (
            <span>
              {me.display_name} <span className={styles.role}>[{me.platform_role}]</span>
            </span>
          ) : (
            <span className={styles.role}>...</span>
          )}
          <Link href="/" className={styles.exit}>← Chat</Link>
        </div>
      </header>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
