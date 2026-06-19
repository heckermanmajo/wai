"""Attachment — Bin-Datei in MinIO, polymorph verknuepft.

minio_key ist der Object-Key im Bucket des Mandanten; sha256 dient zur
Deduplizierung. source markiert die Herkunft (Upload, Voice-Input,
Image-Generation, KI-erzeugtes Artefakt).
"""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.attachment")
class Attachment(BaseMixin, TenantBase):
    __tablename__ = "attachment"

    minio_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime: Mapped[str] = mapped_column(
        String(128), nullable=False, default="application/octet-stream"
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="upload")
    uploader_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
