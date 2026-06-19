"""Audio-Transkription via OpenAI Whisper-Backend.

Wir nutzen ``gpt-4o-transcribe`` (Audio-spezifischer Endpoint — die ueblichen
GPT-5.x-Defaults gelten fuer Audio nicht). Fehler schlagen NICHT durch, sondern
liefern ein dict mit ``error``, damit die Gateway-Route trotzdem die Datei in
MinIO ablegen kann.
"""
from __future__ import annotations

import os
import time
from io import BytesIO

from openai import OpenAI


_EXT_BY_MIME = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
}


def _ext_for(mime: str) -> str:
    if not mime:
        return "webm"
    base = mime.split(";", 1)[0].strip().lower()
    return _EXT_BY_MIME.get(base, "webm")


def transcribe(audio_bytes: bytes, mime: str, language: str = "de") -> dict:
    """Transkribiert ``audio_bytes`` und gibt ``{text, model, duration_seconds}``.

    Bei Fehlern: ``{"text": "", "error": str(e), "model": ..., "duration_seconds": ...}``.
    """
    model = os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe")
    ext = _ext_for(mime)
    started = time.monotonic()
    try:
        client = OpenAI()
        result = client.audio.transcriptions.create(
            model=model,
            file=(f"audio.{ext}", BytesIO(audio_bytes)),
            language=language,
        )
        text = getattr(result, "text", "") or ""
        return {
            "text": text,
            "model": model,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    except Exception as exc:  # noqa: BLE001 — wir wollen jeden Fehler hoeflich zurueckgeben
        return {
            "text": "",
            "error": str(exc),
            "model": model,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
