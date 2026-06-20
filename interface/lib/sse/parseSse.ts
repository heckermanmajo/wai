// SSE-Parser fuer ReadableStream-Chunks. Frames werden bei `\n\n` getrennt,
// `event:` und `data:` Zeilen werden extrahiert. Wir akzeptieren auch Frames
// ohne explizites event-Feld (default: "message").

export interface SseFrame {
  event: string;
  data: string;
}

export class SseParser {
  private buf = "";

  push(chunk: string): SseFrame[] {
    this.buf += chunk;
    const frames: SseFrame[] = [];
    let idx: number;
    while ((idx = this.buf.indexOf("\n\n")) >= 0) {
      const raw = this.buf.slice(0, idx);
      this.buf = this.buf.slice(idx + 2);
      const frame = parseFrame(raw);
      if (frame) frames.push(frame);
    }
    return frames;
  }
}

function parseFrame(raw: string): SseFrame | null {
  if (!raw.trim()) return null;
  let event = "message";
  const dataLines: string[] = [];
  for (const lineRaw of raw.split("\n")) {
    const line = lineRaw.replace(/\r$/, "");
    if (line.startsWith(":")) continue; // comment
    const colon = line.indexOf(":");
    if (colon < 0) continue;
    const field = line.slice(0, colon).trim();
    const value = line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") dataLines.push(value);
  }
  if (!dataLines.length) return null;
  return { event, data: dataLines.join("\n") };
}
