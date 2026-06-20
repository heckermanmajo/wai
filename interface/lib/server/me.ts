// Server-Component-Helper. Holt das /me-Profil mit weitergeleitetem Cookie.
// Bei 401 wird auf /login redirected — Caller braucht das nicht selbst zu pruefen.

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { MeResponse } from "@/lib/api/types";

const BACKEND_URL = process.env.WAI_BACKEND_URL ?? "http://localhost:8500";

export async function requireMe(): Promise<MeResponse> {
  const ck = await cookies();
  const all = ck.getAll().map((c) => `${c.name}=${c.value}`).join("; ");
  const res = await fetch(`${BACKEND_URL}/me`, {
    headers: { Cookie: all },
    cache: "no-store",
  });
  if (res.status === 401) redirect("/login");
  if (!res.ok) {
    throw new Error(`/me lieferte ${res.status}`);
  }
  return (await res.json()) as MeResponse;
}
