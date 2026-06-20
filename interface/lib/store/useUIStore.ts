"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type SidebarTab = "sessions" | "documents";
export type ChatView = "chat" | "mappe";

export interface ToastMsg {
  id: number;
  kind: "ok" | "error" | "info";
  title: string;
  body?: string;
  ttlMs: number;
}

export interface ErrorEntry {
  id: number;
  at: string;
  type: string;
  message: string;
  stack?: string;
  url?: string;
}

interface UIState {
  sidebarTab: SidebarTab;
  setSidebarTab: (t: SidebarTab) => void;

  chatView: ChatView;
  setChatView: (v: ChatView) => void;

  userMenuOpen: boolean;
  setUserMenuOpen: (open: boolean) => void;

  debugCollapsed: boolean;
  toggleDebug: () => void;

  entityOverlay: { cls: string; id: number; label: string } | null;
  openEntity: (cls: string, id: number, label?: string) => void;
  closeEntity: () => void;

  documentOverlay: { docId: number; chatId?: number } | null;
  openDocument: (docId: number, chatId?: number) => void;
  closeDocument: () => void;

  diffOverlay: { docId: number; versionId: number; against: string } | null;
  openDiff: (docId: number, versionId: number, against?: string) => void;
  closeDiff: () => void;

  errors: ErrorEntry[];
  pushError: (e: Omit<ErrorEntry, "id" | "at">) => void;
  clearErrors: () => void;
  errorOverlayOpen: boolean;
  setErrorOverlayOpen: (open: boolean) => void;

  toasts: ToastMsg[];
  pushToast: (t: Omit<ToastMsg, "id">) => void;
  dismissToast: (id: number) => void;
}

let toastSeq = 0;
let errorSeq = 0;

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      sidebarTab: "sessions",
      setSidebarTab: (t) => set({ sidebarTab: t }),

      chatView: "chat",
      setChatView: (v) => set({ chatView: v }),

      userMenuOpen: false,
      setUserMenuOpen: (open) => set({ userMenuOpen: open }),

      debugCollapsed: false,
      toggleDebug: () => set((s) => ({ debugCollapsed: !s.debugCollapsed })),

      entityOverlay: null,
      openEntity: (cls, id, label = "") => set({ entityOverlay: { cls, id, label } }),
      closeEntity: () => set({ entityOverlay: null }),

      documentOverlay: null,
      openDocument: (docId, chatId) => set({ documentOverlay: { docId, chatId } }),
      closeDocument: () => set({ documentOverlay: null }),

      diffOverlay: null,
      openDiff: (docId, versionId, against = "current") =>
        set({ diffOverlay: { docId, versionId, against } }),
      closeDiff: () => set({ diffOverlay: null }),

      errors: [],
      errorOverlayOpen: false,
      pushError: (e) =>
        set((s) => ({
          errors: [
            { ...e, id: ++errorSeq, at: new Date().toISOString() },
            ...s.errors,
          ].slice(0, 200),
          errorOverlayOpen: true,
        })),
      clearErrors: () => set({ errors: [] }),
      setErrorOverlayOpen: (open) => set({ errorOverlayOpen: open }),

      toasts: [],
      pushToast: (t) => {
        const id = ++toastSeq;
        set((s) => ({ toasts: [...s.toasts, { ...t, id }] }));
        if (t.ttlMs > 0) {
          setTimeout(() => get().dismissToast(id), t.ttlMs);
        }
      },
      dismissToast: (id) =>
        set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
    }),
    {
      name: "wai-ui",
      // Nur diese Keys ueberleben Reload — alles andere ist ephemerer UI-State.
      partialize: (state) => ({
        sidebarTab: state.sidebarTab,
        debugCollapsed: state.debugCollapsed,
        chatView: state.chatView,
      }),
    },
  ),
);
