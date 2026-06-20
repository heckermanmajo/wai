import { apiFetch } from "./client";
import type { DevUser, LoginResponse, MeResponse } from "./types";

export function fetchMe(): Promise<MeResponse> {
  // /me darf bei 401 NICHT redirecten — die Login-Page nutzt das, um zu
  // entscheiden ob schon eingeloggt. Server-Components rufen es ebenfalls
  // und konvertieren 401 in einen Redirect via next/navigation.
  return apiFetch<MeResponse>("/api/me", { redirectOn401: false });
}

export function fetchDevUsers(): Promise<{ users: DevUser[] }> {
  return apiFetch<{ users: DevUser[] }>("/api/dev-users", { redirectOn401: false });
}

export function postLogin(login: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/login", {
    method: "POST",
    body: { login, password },
    redirectOn401: false,
  });
}

export function postLoginPick(
  pending_token: string,
  tenant_slug: string,
): Promise<{ status: "ok"; tenant_slug: string; user: { user_id: number; username: string; display_name: string } }> {
  return apiFetch("/api/login/pick", {
    method: "POST",
    body: { token: pending_token, tenant_slug },
    redirectOn401: false,
  });
}

export async function logout(slug: string): Promise<void> {
  // Backend setzt 303 + delete-cookie. fetch folgt redirects standardmaessig,
  // wir brauchen das Resultat nicht — Hauptsache der Cookie ist weg.
  await fetch(`/api/logout/${slug}`, { credentials: "include" });
}
