"""Aktions-System — vorgeschlagene und ausfuehrbare Operationen pro Resource.

Eine Action beschreibt etwas, das ein User mit einer Resource (Document,
Deal, Contact, Chat, ...) tun kann. Sie ist entweder ein vorformulierter
Chat-Task (-> Manager-Agent uebernimmt) oder ein direkter MCP-Tool-Call
(-> ohne Konversations-Loop).

Pattern:
    register_action(Action(
        key="doc.summarize",
        label="Zusammenfassen",
        resource_types=["core.document"],
        execution=ActionExecution(
            kind="chat_task",
            prompt_template="Fasse Dokument #{resource.id} zusammen.",
        ),
    ))

Resource-Typen sind die Polymorph-Aliase aus lib/polymorphic.py
("core.document", "crm.deal", "ai.chat", ...). Leer = globale Aktion
(unabhaengig von einer Resource — z.B. "Neues Document anlegen").

Template-Substitution: {resource.field} oder {resource.field|fallback}
wird per render_template() vor der Ausfuehrung ersetzt. Resource ist
ein dict mit den Feldern der Quell-Entity, plus optional "id", "title",
"name", "type". Substituting nicht-existierender Felder liefert "" oder
den optionalen Default nach "|".
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionExecution(BaseModel):
    """Wie eine Aktion auszufuehren ist.

    kind = "chat_task" → ein neuer (oder existierender) AiChat bekommt
    den substituierten prompt_template als User-Message; Manager-Agent
    laeuft seinen normalen Loop.

    kind = "tool_call" → direkter MCP-Tool-Aufruf mit substituierten
    args (Strings werden via render_template aufgeloest, andere Typen
    bleiben unveraendert).
    """

    kind: Literal["chat_task", "tool_call"]
    prompt_template: str = ""
    tool_name: str = ""
    args: dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    """Eine vorgeschlagene Operation an einer Resource."""

    key: str
    label: str
    description: str = ""
    icon: str = ""
    category: str = "general"
    resource_types: list[str] = Field(default_factory=list)
    execution: ActionExecution
    needs_confirmation: bool = False
    is_destructive: bool = False
    # LLM-Refinement kann diese Felder nachtraeglich setzen
    refine_reason: str = ""
    refine_score: float = 0.0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_REGISTRY: dict[str, Action] = {}


def register_action(action: Action) -> Action:
    """Registriert eine Action. key muss unique sein."""
    if action.key in _REGISTRY:
        raise RuntimeError(
            f"Action-Key {action.key!r} bereits vergeben."
        )
    _REGISTRY[action.key] = action
    return action


def get_action(key: str) -> Action | None:
    return _REGISTRY.get(key)


def list_actions() -> list[Action]:
    return list(_REGISTRY.values())


def list_actions_for_resource(resource_type: str | None) -> list[Action]:
    """Aktionen, die zu resource_type passen.

    None oder Leer-String -> nur globale Aktionen (resource_types=[]).
    Sonst: globale + die mit passendem resource_types-Eintrag.
    """
    if not resource_type:
        return [a for a in _REGISTRY.values() if not a.resource_types]
    return [
        a for a in _REGISTRY.values()
        if not a.resource_types or resource_type in a.resource_types
    ]


def list_global_actions() -> list[Action]:
    return [a for a in _REGISTRY.values() if not a.resource_types]


# ---------------------------------------------------------------------------
# Template-Substitution
# ---------------------------------------------------------------------------


_TEMPLATE_PATTERN = re.compile(r"\{([^{}]+)\}")


def render_template(template: str, context: dict[str, Any]) -> str:
    """Ersetze {path.to.value} bzw. {path|default} aus context."""
    if not template:
        return ""

    def _resolve(expr: str) -> str:
        if "|" in expr:
            key, default = expr.split("|", 1)
        else:
            key, default = expr, ""
        key = key.strip()
        default = default.strip()
        parts = key.split(".")
        cur: Any = context
        try:
            for p in parts:
                if isinstance(cur, dict):
                    cur = cur[p]
                else:
                    cur = getattr(cur, p)
        except (KeyError, AttributeError, TypeError):
            return default
        if cur is None:
            return default
        return str(cur)

    return _TEMPLATE_PATTERN.sub(lambda m: _resolve(m.group(1)), template)


def substitute_args(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Wendet render_template auf alle String-Werte in args an.

    Nicht-Strings bleiben unveraendert. Tiefe Nestung wird nicht
    traversiert — Args sollten flach sein.
    """
    out: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, str):
            out[k] = render_template(v, context)
        else:
            out[k] = v
    return out


def build_resource_context(
    resource: Any,
    alias: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Baut den Kontext fuer Template-Substitution aus einer ORM-Resource.

    Greift gaengige Felder ab und expose sie unter ``resource.*``. extra
    wird flach mergt, ueberschreibt bestehende keys.
    """
    fields = ["id", "title", "name", "first_name", "last_name", "email", "status"]
    resource_dict: dict[str, Any] = {}
    for f in fields:
        val = getattr(resource, f, None)
        if val is not None:
            resource_dict[f] = val
    resource_dict["type"] = alias
    ctx: dict[str, Any] = {"resource": resource_dict}
    if extra:
        ctx.update(extra)
    return ctx


# ---------------------------------------------------------------------------
# Auto-load Registry beim Modul-Import
# ---------------------------------------------------------------------------

# Der Registry-Inhalt wird in lib/actions_registry.py per Side-Effect
# definiert. Wir importieren ihn hier am Ende, damit das einfache
# ``import lib.actions`` reicht, um alle Aktionen verfuegbar zu haben.

def _load_registry() -> None:
    try:
        import lib.actions_registry  # noqa: F401  (Side-Effect: register_action)
    except Exception as exc:  # noqa: BLE001
        # Registry-Datei darf den App-Start nie blockieren. Wir loggen,
        # falls verfuegbar; Fallback: nur globale Aktionen sind leer.
        try:
            from lib.logging import get_logger
            get_logger(__name__).warning(
                "actions_registry konnte nicht geladen werden: %s", exc
            )
        except Exception:
            pass


_load_registry()
