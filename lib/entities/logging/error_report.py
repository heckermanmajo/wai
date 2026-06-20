"""ErrorReport — vom Frontend gemeldeter Fehler (Dev-Mode).

Wird genutzt, wenn der User im Error-Overlay auf "Speichern" klickt:
der serverseitige Stacktrace + sein freier Kommentar + Session-Daten
(URL, Session-ID, User-Agent, letzte User-Nachricht) landen append-only
in logging_db.error_report.
"""
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import LoggingBase
from lib.mixins import BaseMixin


class ErrorReport(BaseMixin, LoggingBase):
    __tablename__ = "error_report"
    # Plan 04: Logging-Tabelle, kein Audit.
    __change_log__ = False

    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status_code: Mapped[int] = mapped_column(nullable=False, default=0)
    error_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stack: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(Text, nullable=False, default="")
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
