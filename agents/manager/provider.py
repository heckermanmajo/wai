"""Hardgecodeter Provider für den manager-Agent.

Modell: GPT-5.5 (CLAUDE.md-Default für alle OpenAI-Implementierungen).
API-Key kommt aus der Umgebungsvariable OPENAI_API_KEY.

Diese Datei ist bewusst der einzige Ort an dem Provider/Modell festgehalten
werden — Manager-Logik importiert MODEL und get_client() und kennt sonst
nichts vom Provider.
"""
import os

from openai import OpenAI

from lib.logging import get_logger

log = get_logger(__name__)

MODEL = "gpt-5.5"

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Lazy-init des OpenAI-Clients. Wirft RuntimeError falls Key fehlt."""
    global _client
    if _client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY ist nicht gesetzt — siehe README → 'Setup'."
            )
        _client = OpenAI()
        log.info("provider initialisiert model=%s", MODEL)
    return _client
