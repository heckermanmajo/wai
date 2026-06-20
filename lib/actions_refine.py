"""LLM-Refinement der Aktions-Vorschlaege.

Hybrid-Pattern: Die statische Registry liefert Kandidaten, ein
Tier-1-LLM (kleines, schnelles Modell) bewertet sie im Kontext der
konkreten Resource und sortiert sie nach Relevanz. Bei Fehlern
(API-Key fehlt, Timeout, JSON-Parsing) wird die Original-Liste
unveraendert zurueckgegeben — Refinement ist immer optional.

Der LLM sieht nur Resource-Metadaten (Type, Name, Short-Abstract)
plus die Liste der Kandidaten — KEINE vollen Markdown-Inhalte, das
waere fuer 5 Kandidaten viel Token-Budget bei wenig Mehrwert.
"""
from __future__ import annotations

import json

from lib.actions import Action
from lib.logging import get_logger

logger = get_logger(__name__)


_REFINE_SYSTEM = (
    "Du rankst Aktions-Vorschlaege fuer eine konkrete Resource (Document/Deal/"
    "Contact/Chat). Du bekommst Resource-Metadaten und eine Liste moeglicher "
    "Aktionen. Liefere ein JSON-Array zurueck mit den Aktions-Keys in absteigender "
    "Relevanz. Format: [{\"key\": \"...\", \"score\": 0.0-1.0, \"reason\": \"max 12 Worte\"}]. "
    "Top-N (max 5) — Filter Aktionen aus, die im Kontext sinnlos sind. Antworte "
    "AUSSCHLIESSLICH mit dem JSON-Array, kein Markdown, kein Text drum herum."
)


def _build_user_prompt(
    resource_type: str,
    resource_name: str,
    resource_short: str,
    candidates: list[Action],
) -> str:
    rows = "\n".join(
        f"- key={a.key} | label={a.label} | desc={a.description}"
        for a in candidates
    )
    return (
        f"Resource-Type: {resource_type}\n"
        f"Name: {resource_name}\n"
        f"Kurzbeschreibung: {resource_short or '(keine)'}\n\n"
        f"Kandidaten:\n{rows}\n\n"
        f"Rank die Kandidaten."
    )


def refine_actions(
    resource_type: str,
    resource_name: str,
    resource_short: str,
    candidates: list[Action],
    *,
    top_n: int = 5,
    timeout_seconds: float = 8.0,
) -> list[Action]:
    """Ranked Liste der Kandidaten via Tier-1-LLM, max top_n Treffer.

    Bei Fehlern: Original-Reihenfolge, abgeschnitten auf top_n.
    """
    if not candidates:
        return []
    # Bei sehr wenigen Kandidaten lohnt sich das Refinement nicht
    if len(candidates) <= 3:
        return candidates[:top_n]

    try:
        from openai import OpenAI  # lazy import — vermeidet harten Fail beim Modul-Load
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY nicht gesetzt")
        model = os.environ.get("TIER_1_MODEL", "gpt-5.4")
        client = OpenAI()
        user_prompt = _build_user_prompt(
            resource_type, resource_name, resource_short, candidates
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _REFINE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            timeout=timeout_seconds,
            response_format={"type": "json_object"},
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("\n") + 1 :] if "\n" in raw else raw
        data = json.loads(raw)
        if isinstance(data, dict) and "items" in data:
            ranked = data["items"]
        elif isinstance(data, list):
            ranked = data
        else:
            ranked = list(data.values())[0] if data else []
    except Exception as exc:  # noqa: BLE001
        logger.info("action refine fallback: %s", exc)
        return candidates[:top_n]

    by_key = {a.key: a for a in candidates}
    ordered: list[Action] = []
    seen: set[str] = set()
    for entry in ranked:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if not key or key not in by_key or key in seen:
            continue
        seen.add(key)
        a = by_key[key].model_copy(update={
            "refine_score": float(entry.get("score") or 0.0),
            "refine_reason": str(entry.get("reason") or "")[:120],
        })
        ordered.append(a)
        if len(ordered) >= top_n:
            break
    # Falls LLM weniger Keys geliefert hat, original tail anhaengen
    for a in candidates:
        if len(ordered) >= top_n:
            break
        if a.key not in seen:
            ordered.append(a)
    return ordered
