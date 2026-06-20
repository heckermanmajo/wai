import { apiFetch } from "./client";
import type { TraceDetailResponse, TraceListResponse } from "./types";

export function fetchTraces(opts: {
  tenant_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<TraceListResponse> {
  const q = new URLSearchParams();
  if (opts.tenant_id) q.set("tenant_id", opts.tenant_id);
  if (opts.status) q.set("status", opts.status);
  if (opts.limit) q.set("limit", String(opts.limit));
  if (opts.offset) q.set("offset", String(opts.offset));
  const qs = q.toString();
  return apiFetch(`/api/traces${qs ? "?" + qs : ""}`, { redirectOn401: false });
}

export function fetchTrace(uid: string): Promise<TraceDetailResponse> {
  return apiFetch(`/api/traces/${uid}`, { redirectOn401: false });
}
