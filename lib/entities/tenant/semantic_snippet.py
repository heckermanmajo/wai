"""SemanticSnippet — Chunk der Markdown-Repraesentation einer Fassade.

fassade_id verweist auf semantic_fassade.id (keine FK-Constraint).
idx ist der 0-basierte Index des Chunks innerhalb der Fassade.

embedding ist eine pgvector-Spalte (1536 Dim, passt zu
``text-embedding-3-small``). Modellwechsel auf andere Dimensionen erfordert
eine neue Alembic-Migration. NULL ist erlaubt — neue Snippets haben bis zum
Embedding-Call kein Vektor.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity

try:
    from pgvector.sqlalchemy import Vector
    _EMBEDDING_COL = Vector(1536)
except ImportError:  # pragma: no cover — Fallback fuer Tooling ohne pgvector
    _EMBEDDING_COL = Text()


@register_entity("semantic.snippet")
class SemanticSnippet(BaseMixin, TenantBase):
    __tablename__ = "semantic_snippet"
    # Plan 04: schreibintensiv durch Re-Embedding-Zyklen, kein Audit-Wert.
    __change_log__ = False

    fassade_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    char_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(
        _EMBEDDING_COL, nullable=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
