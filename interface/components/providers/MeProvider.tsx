"use client";

import { createContext, useContext, useEffect } from "react";
import { useRouter } from "next/navigation";
import type { MeResponse } from "@/lib/api/types";
import { UNAUTHENTICATED_EVENT } from "@/lib/api/client";

const MeContext = createContext<MeResponse | null>(null);

export function useMe(): MeResponse {
  const ctx = useContext(MeContext);
  if (!ctx) throw new Error("useMe muss innerhalb von <MeProvider> stehen");
  return ctx;
}

export function MeProvider({ me, children }: { me: MeResponse; children: React.ReactNode }) {
  const router = useRouter();

  // Globaler 401-Listener: jeder API-Fetch, der eine ungueltige Session entdeckt,
  // feuert UNAUTHENTICATED_EVENT — wir schicken den User dann zum Login.
  useEffect(() => {
    function onUnauth() {
      router.replace("/login");
    }
    window.addEventListener(UNAUTHENTICATED_EVENT, onUnauth);
    return () => window.removeEventListener(UNAUTHENTICATED_EVENT, onUnauth);
  }, [router]);

  return <MeContext.Provider value={me}>{children}</MeContext.Provider>;
}
