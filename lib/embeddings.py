"""OpenAI-Embedding-Provider (sync) fuer die semantische Schicht.

Nutzt den synchronen OpenAI-Client, weil Embeddings im after_commit-Drain
in einem normalen Thread berechnet werden, nicht im async Loop. Modell und
Ziel-Dimension werden ueber Env-Variablen gesteuert; Default ist
``text-embedding-3-small`` mit 1536 Dimensionen.
"""
from __future__ import annotations

import os
import time

from openai import OpenAI

from lib.logging import get_logger

log = get_logger(__name__)

EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = int(os.environ.get("OPENAI_EMBEDDING_DIM", "1536"))

# Modell-Limit ist ~8192 Tokens; wir kappen auf 8000 Zeichen als grosszuegigen
# Puffer (Faustregel ~4 Zeichen/Token => 8000 Zeichen ~ 2000 Tokens, sicher).
_MAX_INPUT_CHARS = 8000

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY ist nicht gesetzt — Embeddings nicht moeglich."
            )
        _client = OpenAI()
        log.info(
            "embeddings provider initialisiert model=%s dim=%s",
            EMBEDDING_MODEL, EMBEDDING_DIM,
        )
    return _client


def embedding_dim() -> int:
    """Konfigurierte Ziel-Dimension (Default 1536, passt zu text-embedding-3-small)."""
    return EMBEDDING_DIM


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-Embedding fuer eine Liste von Strings.

    Reihenfolge bleibt erhalten. Leere Eingabe => leere Ausgabe, kein API-Call.
    Sehr lange Texte werden vor dem API-Call auf ~8000 Zeichen gekappt.
    """
    if not texts:
        return []
    client = _get_client()
    prepared = [(t or "")[:_MAX_INPUT_CHARS] for t in texts]
    started = time.monotonic()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=prepared)
    latency_ms = (time.monotonic() - started) * 1000.0
    vectors = [item.embedding for item in response.data]
    if vectors and len(vectors[0]) != EMBEDDING_DIM:
        log.warning(
            "embedding dim mismatch model=%s got=%d expected=%d",
            EMBEDDING_MODEL, len(vectors[0]), EMBEDDING_DIM,
        )
    log.info(
        "embed_texts model=%s n=%d latency_ms=%.1f",
        EMBEDDING_MODEL, len(prepared), latency_ms,
    )
    return vectors
