"""Polymorphes Verlinken über (target_cls, target_id).

Jede Entity, die polymorph adressierbar sein soll, registriert sich hier
mit einem stabilen String-Alias (z.B. "core.Project", "crm.Contact"). Dieser
Alias wird in Spalten wie `Task.target_cls`, `Note.target_cls`,
`Comment.target_cls`, `TagAssignment.target_cls` gespeichert.

Wir nehmen einen kurzen, sprechenden Alias statt FQCN — überlebt Umbenennungen
im Python-Modul-Pfad und ist für LLMs lesbarer (Debug-MCP exponiert die Aliase).

Nutzung:
    @register_entity("core.Project")
    class Project(TenantBase, BaseMixin):
        ...

    cls = resolve_target_cls("core.Project")     # -> Project
    alias = alias_for(Project)                   # -> "core.Project"
    aliases = list_aliases()                     # -> ["core.Project", ...]
"""
from __future__ import annotations

from typing import Type, TypeVar

T = TypeVar("T")

_alias_to_cls: dict[str, type] = {}
_cls_to_alias: dict[type, str] = {}


def register_entity(alias: str):
    """Class-Decorator: registriert eine SQLAlchemy-Model-Klasse unter alias."""
    def deco(cls: Type[T]) -> Type[T]:
        if alias in _alias_to_cls and _alias_to_cls[alias] is not cls:
            raise RuntimeError(
                f"Alias {alias!r} bereits vergeben für {_alias_to_cls[alias]!r}"
            )
        _alias_to_cls[alias] = cls
        _cls_to_alias[cls] = alias
        return cls
    return deco


def resolve_target_cls(alias: str) -> type | None:
    return _alias_to_cls.get(alias)


def alias_for(cls: type) -> str | None:
    return _cls_to_alias.get(cls)


def list_aliases() -> list[str]:
    return sorted(_alias_to_cls.keys())


def list_entities() -> dict[str, type]:
    return dict(_alias_to_cls)


def is_valid_alias(alias: str) -> bool:
    return alias in _alias_to_cls
