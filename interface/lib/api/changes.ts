import { apiFetch, tenantUrl } from "./client";

export type FieldDiff = {
  field: string;
  old?: unknown;
  new?: unknown;
  truncated?: boolean;
  old_len?: number;
  new_len?: number;
  // Setting-Mini-Audit extra Felder
  scope?: string;
  scope_ref?: string;
  entity_cls?: string;
  entity_id?: number;
  key?: string;
  set_by?: number;
};

export type EntityChange = {
  id: number;
  created_at: string | null;
  tenant_id: string;
  target_cls: string;
  target_id: number;
  change_type: "create" | "update" | "delete" | "soft_delete" | string;
  actor_type: "human" | "ai" | "system" | string;
  actor_id: number;
  agent_name: string;
  trace_uid: string;
  field_diffs: FieldDiff[];
  summary: string;
};

export type EntityChangesResponse = {
  changes: EntityChange[];
  limit: number;
  offset: number;
  count: number;
};

export function fetchEntityChanges(
  slug: string,
  cls: string,
  id: number,
  opts: { limit?: number; offset?: number } = {},
): Promise<EntityChangesResponse> {
  const params = new URLSearchParams();
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.offset) params.set("offset", String(opts.offset));
  const qs = params.toString();
  return apiFetch(
    tenantUrl(slug, `/entity/${cls}/${id}/changes${qs ? "?" + qs : ""}`),
  );
}
