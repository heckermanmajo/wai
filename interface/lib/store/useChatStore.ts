"use client";

import { create } from "zustand";
import type { ChatArtifacts, ChatListItem, MessageDto } from "@/lib/api/types";
import type { TraceEvent } from "@/lib/types/events";

interface ChatState {
  // Liste der Sessions im linken Sidebar-Tab
  chats: ChatListItem[];
  setChats: (chats: ChatListItem[]) => void;

  currentChatId: number | null;
  setCurrentChatId: (id: number | null) => void;

  // Messages pro Chat. Wird nach jedem geladenen Chat / jedem 'done'-Event aktualisiert.
  messagesByChat: Record<number, MessageDto[]>;
  setMessages: (chatId: number, messages: MessageDto[]) => void;
  appendFinalAssistantMessage: (chatId: number, content: string) => void;
  appendUserMessage: (chatId: number, content: string) => void;

  // Mappe pro Chat
  artifactsByChat: Record<number, ChatArtifacts>;
  setArtifacts: (chatId: number, a: ChatArtifacts) => void;

  // Live-Stream-State (nur fuer den aktuell laufenden Trace; null wenn kein Stream)
  streaming: {
    chatId: number;
    traceUid: string;
    statusText: string;
    statusSub: string;
    isDone: boolean;
  } | null;
  setStreaming: (s: ChatState["streaming"]) => void;
  patchStreaming: (patch: Partial<NonNullable<ChatState["streaming"]>>) => void;

  // Debug-Events pro Trace. Capped bei 500 (alte werden gedroppt).
  debugEvents: TraceEvent[];
  pushDebugEvent: (e: TraceEvent) => void;
  resetDebugEvents: () => void;
  debugStats: { events: number; llm: number; tools: number; tokens: number; ms: number };
  patchDebugStats: (patch: Partial<ChatState["debugStats"]>) => void;
}

const EMPTY_STATS = { events: 0, llm: 0, tools: 0, tokens: 0, ms: 0 };

export const useChatStore = create<ChatState>((set) => ({
  chats: [],
  setChats: (chats) => set({ chats }),

  currentChatId: null,
  setCurrentChatId: (id) => set({ currentChatId: id }),

  messagesByChat: {},
  setMessages: (chatId, messages) =>
    set((s) => ({ messagesByChat: { ...s.messagesByChat, [chatId]: messages } })),
  appendFinalAssistantMessage: (chatId, content) =>
    set((s) => {
      const prev = s.messagesByChat[chatId] ?? [];
      const next: MessageDto = {
        id: -Date.now(),
        role: "assistant",
        content,
        tool_call_id: null,
        tool_name: null,
        tool_calls: [],
        created_at: new Date().toISOString(),
      };
      return { messagesByChat: { ...s.messagesByChat, [chatId]: [...prev, next] } };
    }),
  appendUserMessage: (chatId, content) =>
    set((s) => {
      const prev = s.messagesByChat[chatId] ?? [];
      const next: MessageDto = {
        id: -Date.now() - 1,
        role: "user",
        content,
        tool_call_id: null,
        tool_name: null,
        tool_calls: [],
        created_at: new Date().toISOString(),
      };
      return { messagesByChat: { ...s.messagesByChat, [chatId]: [...prev, next] } };
    }),

  artifactsByChat: {},
  setArtifacts: (chatId, a) =>
    set((s) => ({ artifactsByChat: { ...s.artifactsByChat, [chatId]: a } })),

  streaming: null,
  setStreaming: (s) => set({ streaming: s }),
  patchStreaming: (patch) =>
    set((s) => (s.streaming ? { streaming: { ...s.streaming, ...patch } } : s)),

  debugEvents: [],
  pushDebugEvent: (e) =>
    set((s) => {
      const next = [...s.debugEvents, e];
      // Cap: aelteste rauswerfen
      if (next.length > 500) next.splice(0, next.length - 500);
      return { debugEvents: next };
    }),
  resetDebugEvents: () => set({ debugEvents: [], debugStats: { ...EMPTY_STATS } }),
  debugStats: { ...EMPTY_STATS },
  patchDebugStats: (patch) => set((s) => ({ debugStats: { ...s.debugStats, ...patch } })),
}));
