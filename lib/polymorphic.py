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


def validate_target(cls_alias: str, target_id: int) -> None:
    """Prüft ein (target_cls, target_id)-Paar streng vor dem Insert.

    Konvention: leerer Anker (cls_alias="" und target_id=0) ist erlaubt und
    bedeutet "unverankert". Sobald eins der beiden gesetzt ist, müssen beide
    konsistent sein, der Alias muss registriert sein und die ID > 0.
    """
    if cls_alias == "" and target_id == 0:
        return
    if (cls_alias == "") != (target_id == 0):
        raise ValueError(
            f"target_cls und target_id müssen entweder beide leer oder beide "
            f"gesetzt sein (cls={cls_alias!r}, id={target_id})"
        )
    if not is_valid_alias(cls_alias):
        raise ValueError(
            f"Unbekannter target_cls-Alias: {cls_alias!r}. "
            f"Bekannte Aliase: {list_aliases()}"
        )
    if target_id <= 0:
        raise ValueError(
            f"target_id muss > 0 sein, wenn target_cls gesetzt ist "
            f"(cls={cls_alias!r}, id={target_id})"
        )
