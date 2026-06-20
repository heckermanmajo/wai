"use client";

import { useMemo, useRef, useEffect } from "react";
import { marked } from "marked";
import DOMPurify from "isomorphic-dompurify";
import { useUIStore } from "@/lib/store/useUIStore";

// Backend liefert entweder Markdown ODER bereits HTML mit Entity-Links —
// Heuristik: wenn ein <a class="entity-link"...> drin steckt, gilt es als HTML.
const HAS_ENTITY_LINK = /<a\s+class=["']entity-link["']/i;

interface Props {
  content: string;
  className?: string;
  // Wenn true (Streaming-Bubble): tolerantere Parser-Optionen, kein onClick (Streaming-HTML ist noch unvollstaendig)
  streaming?: boolean;
}

const PURIFY_OPTS = {
  ADD_ATTR: ["data-entity", "data-id", "data-bound", "target"],
};

function render(content: string): string {
  if (!content) return "";
  let html: string;
  if (HAS_ENTITY_LINK.test(content)) {
    // Bereits HTML — direkt sanitizen
    html = content;
  } else {
    // Markdown → HTML
    html = marked.parse(content, { async: false, breaks: true, gfm: true }) as string;
  }
  return DOMPurify.sanitize(html, PURIFY_OPTS);
}

export function MarkdownView({ content, className, streaming = false }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const openEntity = useUIStore((s) => s.openEntity);
  const html = useMemo(() => render(content), [content]);

  // Click-Delegation fuer Entity-Links. React-synthetisches Event funktioniert
  // einwandfrei, ein einziger Handler reicht fuer beliebig viele Links.
  function onClick(e: React.MouseEvent<HTMLDivElement>) {
    if (streaming) return;
    const a = (e.target as HTMLElement).closest<HTMLAnchorElement>("a.entity-link");
    if (!a) return;
    const cls = a.getAttribute("data-entity");
    const idStr = a.getAttribute("data-id");
    if (!cls || !idStr) return;
    const id = parseInt(idStr, 10);
    if (!Number.isFinite(id)) return;
    e.preventDefault();
    openEntity(cls, id, a.textContent?.trim() ?? "");
  }

  // Externe Links sollen target=_blank haben
  useEffect(() => {
    if (!ref.current) return;
    ref.current.querySelectorAll<HTMLAnchorElement>("a:not(.entity-link)").forEach((a) => {
      const href = a.getAttribute("href") ?? "";
      if (href.startsWith("http://") || href.startsWith("https://")) {
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener noreferrer");
      }
    });
  }, [html]);

  return (
    <div
      ref={ref}
      className={className}
      onClick={onClick}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
