import { apiFetch, tenantUrl } from "./client";
import type { ActionRunResult, ActionsResponse } from "./types";

export function listActions(
  slug: string,
  opts: { cls?: string; id?: number; refine?: boolean; limit?: number } = {},
): Promise<ActionsResponse> {
  const q = new URLSearchParams();
  if (opts.cls) q.set("cls", opts.cls);
  if (opts.id) q.set("id", String(opts.id));
  if (opts.refine) q.set("refine", "true");
  if (opts.limit) q.set("limit", String(opts.limit));
  const qs = q.toString();
  return apiFetch(tenantUrl(slug, `/actions${qs ? "?" + qs : ""}`));
}

export function runAction(
  slug: string,
  body: { action_key: string; cls?: string; id?: number; chat_id?: number },
): Promise<ActionRunResult> {
  return apiFetch(tenantUrl(slug, "/actions/run"), { method: "POST", body });
}
