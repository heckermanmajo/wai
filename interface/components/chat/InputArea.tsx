"use client";

import { useRef, useState } from "react";
import { useChatStore } from "@/lib/store/useChatStore";
import { useChatStream } from "@/lib/sse/useChatStream";
import { createChat } from "@/lib/api/chats";
import { ingestImage, ingestVoice } from "@/lib/api/ingest";
import { useUIStore } from "@/lib/store/useUIStore";
import styles from "./InputArea.module.css";

export function InputArea({ slug }: { slug: string }) {
  const [value, setValue] = useState("");
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  const currentChatId = useChatStore((s) => s.currentChatId);
  const setCurrentChatId = useChatStore((s) => s.setCurrentChatId);
  const streaming = useChatStore((s) => s.streaming);
  const pushToast = useUIStore((s) => s.pushToast);
  const { send } = useChatStream(slug);

  const disabled = !!streaming && !streaming.isDone;

  function autosize() {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 140) + "px";
  }

  async function onSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    const text = value.trim();
    if (!text || disabled) return;
    let chatId = currentChatId;
    if (!chatId) {
      const c = await createChat(slug, "");
      chatId = c.id;
      setCurrentChatId(chatId);
    }
    setValue("");
    autosize();
    send(chatId, text);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void onSubmit();
    }
  }

  async function onPickImage(file: File) {
    if (!currentChatId) {
      const c = await createChat(slug, "");
      setCurrentChatId(c.id);
    }
    try {
      const r = await ingestImage(slug, file, currentChatId ?? 0);
      pushToast({ kind: "ok", title: "Bild hochgeladen", body: r.minio_key, ttlMs: 6000 });
    } catch (e) {
      pushToast({ kind: "error", title: "Upload fehlgeschlagen", body: String(e), ttlMs: 8000 });
    }
  }

  async function toggleRecord() {
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      rec.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        let chatId = currentChatId;
        if (!chatId) {
          const c = await createChat(slug, "");
          chatId = c.id;
          setCurrentChatId(chatId);
        }
        try {
          const r = await ingestVoice(slug, blob, chatId);
          if (r.transcript) {
            setValue((v) => (v ? v + " " + r.transcript : r.transcript));
            setTimeout(autosize, 0);
          }
          if (r.transcribe_error) {
            pushToast({ kind: "error", title: "Transkription fehlgeschlagen", body: r.transcribe_error, ttlMs: 8000 });
          }
        } catch (e) {
          pushToast({ kind: "error", title: "Voice-Upload fehlgeschlagen", body: String(e), ttlMs: 8000 });
        }
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
    } catch (e) {
      pushToast({ kind: "error", title: "Mikrofon nicht verfuegbar", body: String(e), ttlMs: 8000 });
    }
  }

  return (
    <form onSubmit={onSubmit} className={styles.form}>
      <textarea
        ref={taRef}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          autosize();
        }}
        onKeyDown={onKeyDown}
        placeholder="Frag wai etwas… (Enter zum Senden, Shift+Enter fuer Zeilenumbruch)"
        disabled={disabled}
        rows={1}
        className={styles.ta}
      />
      <div className={styles.buttons}>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void onPickImage(f);
            e.target.value = "";
          }}
        />
        <button type="button" onClick={() => fileRef.current?.click()} title="Bild hochladen">
          Bild
        </button>
        <button type="button" onClick={toggleRecord} data-recording={recording ? "1" : "0"}>
          {recording ? "Stop" : "Mic"}
        </button>
        <button type="submit" className="primary" disabled={disabled || !value.trim()}>
          Senden
        </button>
      </div>
    </form>
  );
}
