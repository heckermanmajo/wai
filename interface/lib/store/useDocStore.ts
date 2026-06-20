"use client";

import { create } from "zustand";
import type { DocumentDetail, DocumentListItem, DocumentVersionDetail } from "@/lib/api/types";

interface DocState {
  // Liste der Dokumente fuer den Documents-Tab (Cache)
  allDocs: DocumentListItem[];
  setAllDocs: (docs: DocumentListItem[]) => void;
  searchFilter: string;
  setSearchFilter: (q: string) => void;

  // Currently opened (in Overlay)
  current: DocumentDetail | null;
  setCurrent: (doc: DocumentDetail | null) => void;
  dirty: boolean;
  setDirty: (b: boolean) => void;

  viewingVersionId: number | null;
  setViewingVersionId: (id: number | null) => void;
  viewingVersion: DocumentVersionDetail | null;
  setViewingVersion: (v: DocumentVersionDetail | null) => void;

  autosaveOn: boolean;
  setAutosaveOn: (b: boolean) => void;
}

export const useDocStore = create<DocState>((set) => ({
  allDocs: [],
  setAllDocs: (docs) => set({ allDocs: docs }),
  searchFilter: "",
  setSearchFilter: (q) => set({ searchFilter: q }),

  current: null,
  setCurrent: (doc) => set({ current: doc, dirty: false }),
  dirty: false,
  setDirty: (b) => set({ dirty: b }),

  viewingVersionId: null,
  setViewingVersionId: (id) => set({ viewingVersionId: id }),
  viewingVersion: null,
  setViewingVersion: (v) => set({ viewingVersion: v }),

  autosaveOn: false,
  setAutosaveOn: (b) => set({ autosaveOn: b }),
}));
