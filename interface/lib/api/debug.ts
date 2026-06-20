import { apiFetch } from "./client";
import type { TraceDetailResponse, TraceRow } from "./types";

export type DebugMe = {
  user_id: number;
  username: string;
  display_name: string;
  platform_role: "admin" | "supporter" | string;
  memberships: string[];
};

export type DebugMcpToolInfo = {
  name: string;
  kind?: string;
  description?: string;
};

export type DebugMcpEntry = {
  name: string;
  url: string;
  status: "online" | "offline" | "unknown" | string;
  kind: string;
  description: string;
  version: string;
  tools: DebugMcpToolInfo[];
  error?: string;
};

export type DebugMcpCall = {
  sequence: number;
  timestamp: string | null;
  event_type: string;
  trace_uid: string;
  data: Record<string, unknown>;
};

export function fetchDebugMe(): Promise<DebugMe> {
  return apiFetch("/api/debug/me", { redirectOn401: false });
}

export function fetchDebugTraces(opts: {
  tenant_id?: string;
  status?: string;
  intent?: string;
  min_duration?: number;
  max_duration?: number;
  limit?: number;
  offset?: number;
} = {}): Promise<{ traces: TraceRow[]; limit: number; offset: number; count: number }> {
  const q = new URLSearchParams();
  if (opts.tenant_id) q.set("tenant_id", opts.tenant_id);
  if (opts.status) q.set("status", opts.status);
  if (opts.intent) q.set("intent", opts.intent);
  if (opts.min_duration != null) q.set("min_duration", String(opts.min_duration));
  if (opts.max_duration != null) q.set("max_duration", String(opts.max_duration));
  if (opts.limit) q.set("limit", String(opts.limit));
  if (opts.offset) q.set("offset", String(opts.offset));
  const qs = q.toString();
  return apiFetch(`/api/debug/traces${qs ? "?" + qs : ""}`, { redirectOn401: false });
}

export function fetchDebugTrace(uid: string): Promise<TraceDetailResponse> {
  return apiFetch(`/api/debug/traces/${uid}`, { redirectOn401: false });
}

export function fetchDebugMcps(): Promise<{ mcps: DebugMcpEntry[]; count: number }> {
  return apiFetch("/api/debug/mcps", { redirectOn401: false });
}

export function fetchDebugMcp(name: string): Promise<DebugMcpEntry> {
  return apiFetch(`/api/debug/mcps/${name}`, { redirectOn401: false });
}

export function fetchDebugMcpCalls(
  name: string,
  limit = 50,
): Promise<{ calls: DebugMcpCall[]; count: number }> {
  return apiFetch(`/api/debug/mcps/${name}/calls?limit=${limit}`, {
    redirectOn401: false,
  });
}
