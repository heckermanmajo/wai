"""pgvector embeddings

Revision ID: tenant_0007
Revises: tenant_0006
Create Date: 2026-06-20

Aktiviert die pgvector-Extension (idempotent, falls bei alten Tenants noch
nicht passiert) und migriert ``semantic_snippet.embedding`` von TEXT
auf ``vector(1536)``. Alter Inhalt wird verworfen, da bislang nur leere
Platzhalter geschrieben wurden. Cosine-Index (ivfflat) wird gleich
mitangelegt — leere Tabelle ist ok.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "tenant_0007"
down_revision: Union[str, None] = "tenant_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Alte TEXT-Spalte droppen — Inhalt ist sowieso leer (Platzhalter).
    op.execute("ALTER TABLE semantic_snippet DROP COLUMN IF EXISTS embedding")
    op.execute(
        "ALTER TABLE semantic_snippet ADD COLUMN embedding vector(1536) NULL"
    )

    # Cosine-Index — leere Tabelle ist ok, ivfflat funktioniert spaeter auch.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_semantic_snippet_embedding "
        "ON semantic_snippet USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_semantic_snippet_embedding")
    op.execute("ALTER TABLE semantic_snippet DROP COLUMN IF EXISTS embedding")
    op.execute(
        "ALTER TABLE semantic_snippet "
        "ADD COLUMN embedding TEXT NOT NULL DEFAULT ''"
    )
