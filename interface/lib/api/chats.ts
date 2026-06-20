import { apiFetch, tenantUrl } from "./client";
import type { ChatArtifacts, ChatDetail, ChatListItem } from "./types";

export function fetchChats(slug: string): Promise<{ chats: ChatListItem[] }> {
  return apiFetch(tenantUrl(slug, "/chats"));
}

export function fetchChat(slug: string, chatId: number): Promise<ChatDetail> {
  return apiFetch(tenantUrl(slug, `/chats/${chatId}`));
}

export function createChat(slug: string, title = ""): Promise<{ id: number; title: string }> {
  return apiFetch(tenantUrl(slug, "/chats"), { method: "POST", body: { title } });
}

export function updateChat(
  slug: string,
  chatId: number,
  patch: { title?: string },
): Promise<{ id: number; title: string }> {
  return apiFetch(tenantUrl(slug, `/chats/${chatId}`), { method: "PATCH", body: patch });
}

export function cloneChat(slug: string, chatId: number): Promise<{ id: number; source_id: number }> {
  return apiFetch(tenantUrl(slug, `/chats/${chatId}/clone`), { method: "POST", body: {} });
}

export function shareChat(slug: string, chatId: number, shared: boolean): Promise<{ id: number; is_shared: boolean }> {
  return apiFetch(tenantUrl(slug, `/chats/${chatId}/share`), { method: "POST", body: { shared } });
}

export function deleteChat(slug: string, chatId: number): Promise<{ id: number; is_deleted: boolean }> {
  return apiFetch(tenantUrl(slug, `/chats/${chatId}`), { method: "DELETE" });
}

export function fetchChatArtifacts(slug: string, chatId: number): Promise<ChatArtifacts> {
  return apiFetch(tenantUrl(slug, `/chats/${chatId}/artifacts`));
}
