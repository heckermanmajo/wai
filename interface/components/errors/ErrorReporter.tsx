"use client";

import { useEffect } from "react";
import { useUIStore } from "@/lib/store/useUIStore";

// Hookt globale Fehler ins useUIStore — Error-Overlay-Badge inkrementiert sich live.
// Zusaetzlich posten wir Reports an /api/errors/report (Backend-Endpoint).
export function ErrorReporter() {
  const pushError = useUIStore((s) => s.pushError);

  useEffect(() => {
    function report(type: string, message: string, stack?: string) {
      pushError({ type, message, stack, url: window.location.href });
      // Beste-Bemuehung: an Backend, aber Fehler hier nie weiter eskalieren
      fetch("/api/errors/report", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: window.location.href,
          error_type: type,
          message,
          stack: stack ?? "",
          user_agent: navigator.userAgent,
        }),
      }).catch(() => {});
    }

    function onError(ev: ErrorEvent) {
      report(ev.error?.name ?? "Error", ev.message, ev.error?.stack);
    }
    function onRejection(ev: PromiseRejectionEvent) {
      const r = ev.reason;
      const msg = r instanceof Error ? r.message : String(r);
      const stack = r instanceof Error ? r.stack : undefined;
      report("UnhandledRejection", msg, stack);
    }

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, [pushError]);

  return null;
}
