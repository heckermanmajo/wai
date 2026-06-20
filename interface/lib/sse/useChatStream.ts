"use client";

import { useCallback, useEffect, useRef } from "react";
import { useChatStore } from "@/lib/store/useChatStore";
import { useUIStore } from "@/lib/store/useUIStore";
import { tenantUrl } from "@/lib/api/client";
import type {
  DoneEnvelope,
  LlmDeltaData,
  LlmResponseData,
  ToolCallStartedData,
  ToolCallResultData,
  TraceEnvelope,
  TraceEvent,
} from "@/lib/types/events";
import { streamBus } from "./streamBus";
import { SseParser } from "./parseSse";

interface SendOptions {
  onDone?: (final: DoneEnvelope) => void;
  onError?: (msg: string) => void;
}

function statusForEvent(ev: TraceEvent): { text: string; sub: string } | null {
  switch (ev.event_type) {
    case "trace_started":
      return { text: "Starte…", sub: "" };
    case "intent_classified": {
      const intent = String(ev.data?.intent ?? "");
      return { text: "Plane Antwort…", sub: intent ? `Intent: ${intent}` : "" };
    }
    case "llm_request": {
      const round = Number(ev.data?.round ?? 1);
      return {
        text: round > 1 ? `Denke nach (Runde ${round})…` : "Schreibt Antwort…",
        sub: "",
      };
    }
    case "tool_call_started": {
      const tool = String((ev.data as ToolCallStartedData)?.tool_name ?? "Tool");
      return { text: `Nutze ${tool}…`, sub: "" };
    }
    case "llm_response":
      return { text: "Antwort empfangen", sub: "" };
    case "trace_completed":
      return { text: "Fertig", sub: "" };
    default:
      return null;
  }
}

/**
 * Sendet eine User-Message und streamt die SSE-Response des Manager-Agenten.
 *
 * Delta-Text wird NICHT in den Zustand-Store geschrieben (sonst re-rendered alle
 * Subscriber bei jedem Token). Stattdessen geht jeder Delta in den streamBus,
 * den nur die <StreamingBubble> abonniert.
 */
export function useChatStream(slug: string) {
  const ctrlRef = useRef<AbortController | null>(null);
  const appendUser = useChatStore((s) => s.appendUserMessage);
  const appendAssistant = useChatStore((s) => s.appendFinalAssistantMessage);
  const setStreaming = useChatStore((s) => s.setStreaming);
  const patchStreaming = useChatStore((s) => s.patchStreaming);
  const pushDebug = useChatStore((s) => s.pushDebugEvent);
  const patchStats = useChatStore((s) => s.patchDebugStats);
  const resetDebug = useChatStore((s) => s.resetDebugEvents);
  const pushError = useUIStore((s) => s.pushError);

  const abort = useCallback(() => {
    ctrlRef.current?.abort();
    ctrlRef.current = null;
  }, []);

  useEffect(() => abort, [abort]);

  const send = useCallback(
    async (chatId: number, message: string, opts: SendOptions = {}) => {
      abort();
      const ctrl = new AbortController();
      ctrlRef.current = ctrl;

      appendUser(chatId, message);
      streamBus.reset(true);
      resetDebug();
      setStreaming({
        chatId,
        traceUid: "",
        statusText: "Sende…",
        statusSub: "",
        isDone: false,
      });

      let finalResponse = "";
      let llmCount = 0;
      let toolCount = 0;
      let promptTokens = 0;
      let completionTokens = 0;
      const t0 = performance.now();

      try {
        const res = await fetch(tenantUrl(slug, `/chats/${chatId}/messages`), {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({ message }),
          signal: ctrl.signal,
        });

        if (!res.ok || !res.body) {
          const txt = await res.text().catch(() => "");
          throw new Error(`Stream ${res.status}: ${txt || "kein Body"}`);
        }

        const parser = new SseParser();
        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          for (const frame of parser.push(chunk)) {
            if (frame.event === "trace") {
              const env = JSON.parse(frame.data) as TraceEnvelope;
              patchStreaming({ traceUid: env.trace_uid });
              continue;
            }
            if (frame.event === "done") {
              const env = JSON.parse(frame.data) as DoneEnvelope;
              finalResponse = env.response || streamBus.current();
              patchStreaming({
                statusText: env.status === "ok" ? "Fertig" : "Fehler",
                statusSub: env.error_message || "",
                isDone: true,
              });
              continue;
            }
            if (frame.event !== "event") continue;
            const ev = JSON.parse(frame.data) as TraceEvent;

            if (ev.event_type === "llm_delta") {
              const d = ev.data as LlmDeltaData;
              if (d.content_delta) streamBus.append(d.content_delta);
              // llm_delta ist volatil — nicht in debug-Events einfuegen
              continue;
            }

            // Debug-Panel
            pushDebug(ev);
            patchStats({ events: (useChatStore.getState().debugStats.events ?? 0) + 1 });

            // Reset Streaming-Bubble pro neuer LLM-Runde (Multi-Tool-Reasoning)
            if (ev.event_type === "llm_request" && llmCount > 0) {
              streamBus.reset(true);
            }

            if (ev.event_type === "llm_request") {
              llmCount += 1;
              patchStats({ llm: llmCount });
            }
            if (ev.event_type === "tool_call_started") {
              toolCount += 1;
              patchStats({ tools: toolCount });
            }
            if (ev.event_type === "llm_response") {
              const d = ev.data as LlmResponseData;
              promptTokens += d.prompt_tokens ?? 0;
              completionTokens += d.completion_tokens ?? 0;
              patchStats({ tokens: promptTokens + completionTokens });
            }

            const status = statusForEvent(ev);
            if (status) patchStreaming({ statusText: status.text, statusSub: status.sub });

            patchStats({ ms: Math.round(performance.now() - t0) });
          }
        }

        // Stream fertig → finale Message ins Store
        appendAssistant(chatId, finalResponse || streamBus.current());
        streamBus.setCaret(false);
        patchStreaming({ isDone: true });
        opts.onDone?.({
          trace_uid: useChatStore.getState().streaming?.traceUid ?? "",
          status: "ok",
          response: finalResponse,
          intent: "",
          tool_calls: [],
          duration_ms: Math.round(performance.now() - t0),
          error_message: "",
          chat_id: chatId,
        });
        setStreaming(null);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        const msg = err instanceof Error ? err.message : String(err);
        pushError({ type: "ChatStream", message: msg });
        opts.onError?.(msg);
        patchStreaming({ statusText: "Fehler", statusSub: msg, isDone: true });
        setStreaming(null);
      } finally {
        if (ctrlRef.current === ctrl) ctrlRef.current = null;
      }
    },
    [
      slug,
      appendUser,
      appendAssistant,
      setStreaming,
      patchStreaming,
      pushDebug,
      patchStats,
      resetDebug,
      pushError,
      abort,
    ],
  );

  return { send, abort };
}
