"""Mixins für alle DataClasses.

Jede Entity bekommt:
    - id           (PK, autoincrement)
    - created_at   (UTC, by DB default)
    - updated_at   (UTC, by DB default, ON UPDATE via SQLAlchemy)
    - is_deleted   (Soft-Delete-Flag)

Wir verwenden **keine** Foreign-Key-Constraints — alle Beziehungen sind
nackte Integer-IDs. Bewusste Entscheidung: weniger Migrations-Schmerz,
einfacheres Cross-DB-Referenzieren (admin -> tenant), polymorphes
Verlinken ohne Spezial-Tricks.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column


class IdMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BaseMixin(IdMixin, TimestampMixin, SoftDeleteMixin):
    """Sammel-Mixin — die meisten Entities erben das."""
