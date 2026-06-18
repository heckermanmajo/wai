"""Two-tier LLM provider for manager-agent.

Tier 1 (gpt-5.4): Fast intent classification.
Tier 2 (gpt-5.5): Complex reasoning, tool-calling, response generation.
"""
import os

from openai import AsyncOpenAI

from lib.logging import get_logger

log = get_logger(__name__)

TIER_1_MODEL = os.environ.get("TIER_1_MODEL", "gpt-5.4")
TIER_2_MODEL = os.environ.get("TIER_2_MODEL", "gpt-5.5")

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt.")
        _client = AsyncOpenAI()
        log.info("provider initialisiert tier1=%s tier2=%s", TIER_1_MODEL, TIER_2_MODEL)
    return _client


def get_tier1_model() -> str:
    return TIER_1_MODEL


def get_tier2_model() -> str:
    return TIER_2_MODEL
