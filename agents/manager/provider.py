"""Two-tier LLM provider for manager-agent.

Tier 1 (gpt-5.4): Fast intent classification.
Tier 2 (gpt-5.5): Complex reasoning, tool-calling, response generation.

Plan 03 — Tier 2 (Default-Modell fuer Reasoning + Tool-Calls) wird ueber
``lib.settings.resolve("agent.model.default", tenant=...)`` aufgeloest.
Plattform-Default kommt aus ``PLATFORM_DEFAULTS``, kann pro Tenant in der
Setting-Tabelle ueberschrieben werden. Tier 1 bleibt env-getrieben, weil
der schnelle Intent-Klassifizierer nicht pro Tenant variieren soll.
"""
import os

from openai import AsyncOpenAI

from lib.logging import get_logger
from lib.settings import resolve
from lib.tenant_context import get_tenant

log = get_logger(__name__)

TIER_1_MODEL = os.environ.get("TIER_1_MODEL", "gpt-5.4")
# Fallback, wenn weder DB- noch ContextVar-Tenant verfuegbar ist.
TIER_2_MODEL_FALLBACK = os.environ.get("TIER_2_MODEL", "gpt-5.5")

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt.")
        _client = AsyncOpenAI()
        log.info(
            "provider initialisiert tier1=%s tier2_fallback=%s",
            TIER_1_MODEL, TIER_2_MODEL_FALLBACK,
        )
    return _client


def get_tier1_model() -> str:
    return TIER_1_MODEL


def get_tier2_model() -> str:
    """Setting-Resolver -> agent.model.default mit Tenant-Kontext."""
    tenant = get_tenant()
    try:
        return str(resolve("agent.model.default", tenant=tenant))
    except Exception:
        # Resolver-Fehler (DB nicht da, Key fehlt) duerfen den Chat nicht killen.
        log.warning("settings_resolve_failed_for_tier2", exc_info=True)
        return TIER_2_MODEL_FALLBACK
