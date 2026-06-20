import { tenantUrl } from "./client";
import type { IngestImageResponse, IngestVoiceResponse } from "./types";

export async function ingestVoice(
  slug: string,
  file: Blob,
  chatId: number,
): Promise<IngestVoiceResponse> {
  const form = new FormData();
  form.append("file", file, "voice.webm");
  const res = await fetch(tenantUrl(slug, `/ingest/voice?chat_id=${chatId}`), {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) throw new Error(`Voice-Ingest fehlgeschlagen: ${res.status}`);
  return (await res.json()) as IngestVoiceResponse;
}

export async function ingestImage(
  slug: string,
  file: File,
  chatId: number,
): Promise<IngestImageResponse> {
  const form = new FormData();
  form.append("file", file, file.name || "image.png");
  const res = await fetch(tenantUrl(slug, `/ingest/image?chat_id=${chatId}`), {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) throw new Error(`Image-Ingest fehlgeschlagen: ${res.status}`);
  return (await res.json()) as IngestImageResponse;
}
