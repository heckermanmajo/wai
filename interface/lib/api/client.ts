// Schmaler fetch-Wrapper.
// Alle Backend-Calls laufen Same-Origin via next.config.ts rewrites — daher
// reichen relative Pfade unter /api/*. credentials:"include" sendet das
// wai_session-Cookie automatisch mit. 401 triggert globalen Redirect via
// CustomEvent, das die App im Layout lauscht.

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `Backend ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export const UNAUTHENTICATED_EVENT = "wai:unauthenticated";

function emitUnauthenticated() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(UNAUTHENTICATED_EVENT));
}

async function parseBody(res: Response): Promise<unknown> {
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    try {
      return await res.json();
    } catch {
      return null;
    }
  }
  return await res.text();
}

export interface ApiOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  // Wenn true (default), wird bei 401 ein CustomEvent gefeuert und ApiError geworfen.
  // Login-Page setzt das auf false, weil 401 dort "falsches Passwort" bedeutet, nicht "logout".
  redirectOn401?: boolean;
}

export async function apiFetch<T = unknown>(
  path: string,
  opts: ApiOptions = {},
): Promise<T> {
  const { body, redirectOn401 = true, headers, ...rest } = opts;

  const init: RequestInit = {
    ...rest,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(headers ?? {}),
    },
  };
  if (body !== undefined) {
    init.body = typeof body === "string" ? body : JSON.stringify(body);
  }

  const res = await fetch(path, init);
  if (res.status === 401 && redirectOn401) {
    emitUnauthenticated();
  }
  if (!res.ok) {
    const detail = await parseBody(res);
    const msg =
      typeof detail === "object" && detail && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Backend ${res.status}`;
    throw new ApiError(res.status, detail, msg);
  }
  if (res.status === 204) return null as T;
  return (await parseBody(res)) as T;
}

// Convenience: tenant-scoped Backend-URLs (siehe next.config.ts rewrite)
export function tenantUrl(slug: string, path: string): string {
  // Erlaubt sowohl "/chats" als auch "chats"
  const clean = path.startsWith("/") ? path.slice(1) : path;
  return `/api/backend/${slug}/${clean}`;
}
