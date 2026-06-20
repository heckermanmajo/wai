import { apiFetch, tenantUrl } from "./client";
import type {
  DocumentDetail,
  DocumentDiff,
  DocumentListItem,
  DocumentVersionDetail,
  DocumentVersionListItem,
} from "./types";

export function listDocuments(
  slug: string,
  opts: { target_cls?: string; target_id?: number; limit?: number } = {},
): Promise<{ documents: DocumentListItem[] }> {
  const q = new URLSearchParams();
  if (opts.target_cls) q.set("target_cls", opts.target_cls);
  if (opts.target_id) q.set("target_id", String(opts.target_id));
  if (opts.limit) q.set("limit", String(opts.limit));
  const qs = q.toString();
  return apiFetch(tenantUrl(slug, `/documents${qs ? "?" + qs : ""}`));
}

export function getDocument(slug: string, docId: number): Promise<DocumentDetail> {
  return apiFetch(tenantUrl(slug, `/documents/${docId}`));
}

export function createDocument(
  slug: string,
  body: { title?: string; content?: string; target_cls?: string; target_id?: number } = {},
): Promise<DocumentDetail> {
  return apiFetch(tenantUrl(slug, "/documents"), { method: "POST", body });
}

export function updateDocument(
  slug: string,
  docId: number,
  body: { title?: string; content?: string; target_cls?: string; target_id?: number },
): Promise<DocumentDetail> {
  return apiFetch(tenantUrl(slug, `/documents/${docId}`), { method: "PUT", body });
}

export function deleteDocument(slug: string, docId: number): Promise<{ id: number; is_deleted: boolean }> {
  return apiFetch(tenantUrl(slug, `/documents/${docId}`), { method: "DELETE" });
}

export function listVersions(
  slug: string,
  docId: number,
  limit = 100,
): Promise<{ versions: DocumentVersionListItem[] }> {
  return apiFetch(tenantUrl(slug, `/documents/${docId}/versions?limit=${limit}`));
}

export function getVersion(
  slug: string,
  docId: number,
  versionId: number,
): Promise<DocumentVersionDetail> {
  return apiFetch(tenantUrl(slug, `/documents/${docId}/versions/${versionId}`));
}

export function restoreVersion(
  slug: string,
  docId: number,
  versionId: number,
): Promise<DocumentDetail> {
  return apiFetch(tenantUrl(slug, `/documents/${docId}/versions/${versionId}/restore`), {
    method: "POST",
    body: {},
  });
}

export function diffVersion(
  slug: string,
  docId: number,
  versionId: number,
  against: string = "current",
): Promise<DocumentDiff> {
  return apiFetch(tenantUrl(slug, `/documents/${docId}/versions/${versionId}/diff?against=${encodeURIComponent(against)}`));
}
