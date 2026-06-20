"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { fetchDevUsers, fetchMe, postLogin, postLoginPick } from "@/lib/api/me";
import type { DevUser } from "@/lib/api/types";
import styles from "./login.module.css";

interface PickerState {
  pending_token: string;
  tenants: { slug: string; name: string }[];
}

export default function LoginPage() {
  // useSearchParams triggert CSR-Bailout — Suspense-Boundary ist Pflicht in Next 15.
  return (
    <Suspense fallback={<div className={styles.wrap}><div className={styles.card}>…</div></div>}>
      <LoginInner />
    </Suspense>
  );
}

function LoginInner() {
  const router = useRouter();
  const search = useSearchParams();
  const nextPath = search.get("next") ?? "";

  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [picker, setPicker] = useState<PickerState | null>(null);
  const [devUsers, setDevUsers] = useState<DevUser[]>([]);

  // Auto-Redirect, wenn schon eingeloggt
  useEffect(() => {
    fetchMe()
      .then((me) => {
        const target = nextPath && nextPath.startsWith("/") ? nextPath : `/${me.tenant_slug}`;
        router.replace(target);
      })
      .catch(() => {});
  }, [router, nextPath]);

  useEffect(() => {
    fetchDevUsers()
      .then((r) => setDevUsers(r.users))
      .catch(() => setDevUsers([]));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const r = await postLogin(login.trim(), password);
      if (r.status === "ok") {
        router.replace(nextPath && nextPath.startsWith("/") ? nextPath : `/${r.tenant_slug}`);
        return;
      }
      setPicker({ pending_token: r.pending_token, tenants: r.tenants });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onPickTenant(slug: string) {
    if (!picker) return;
    setBusy(true);
    setErr("");
    try {
      const r = await postLoginPick(picker.pending_token, slug);
      router.replace(`/${r.tenant_slug}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function fillDevUser(u: DevUser) {
    setLogin(u.username);
    setPassword("123"); // Dev-Default-Passwort (siehe gateway/ui_login.py)
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <h1 className={styles.title}>wai · Login</h1>

        {!picker && (
          <form onSubmit={onSubmit} className={styles.form}>
            <label className={styles.field}>
              <span>Login / E-Mail</span>
              <input
                type="text"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                autoFocus
                autoComplete="username"
              />
            </label>
            <label className={styles.field}>
              <span>Passwort</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            {err && <div className={styles.err}>{err}</div>}
            <button type="submit" className="primary" disabled={busy || !login || !password}>
              {busy ? "…" : "Einloggen"}
            </button>
          </form>
        )}

        {picker && (
          <div className={styles.picker}>
            <p>Mehrere Tenants — bitte auswaehlen:</p>
            {picker.tenants.map((t) => (
              <button
                key={t.slug}
                className={styles.tenantBtn}
                disabled={busy}
                onClick={() => onPickTenant(t.slug)}
              >
                <strong>{t.name}</strong>
                <small>{t.slug}</small>
              </button>
            ))}
            {err && <div className={styles.err}>{err}</div>}
            <button onClick={() => setPicker(null)} className={styles.cancel}>
              Zurueck
            </button>
          </div>
        )}
      </div>

      {!picker && devUsers.length > 0 && (
        <div className={styles.devCard}>
          <div className={styles.devTitle}>Dev-User (Passwort: <code>123</code>)</div>
          <ul className={styles.devList}>
            {devUsers.map((u) => (
              <li key={u.username}>
                <button onClick={() => fillDevUser(u)} className={styles.devBtn}>
                  <strong>{u.display_name}</strong>
                  <span>{u.username}</span>
                  <small>{u.tenants.join(", ")}</small>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
