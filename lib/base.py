"""Drei SQLAlchemy-Declarative-Bases — eine pro logischer DB.

Trennung in eigene Bases stellt sicher, dass jede DB ihre eigene MetaData hat.
Alembic kann dann pro Base eine eigene Migrations-Historie führen.

- AdminBase   -> admin_db   (Tenants, UserData, AiProvider, ...)
- LoggingBase -> logging_db (RequestLog, EventLog, LogEntry, CronWorker, ...)
- TenantBase  -> tenant_<slug> (Project, Task, Contact, Deal, AiChat, ...)
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class AdminBase(DeclarativeBase):
    """Tabellen in admin_db (zentral, mandantenübergreifend)."""


class LoggingBase(DeclarativeBase):
    """Tabellen in logging_db (zentral, append-only Telemetrie)."""


class TenantBase(DeclarativeBase):
    """Tabellen in tenant_<slug> (eine physische DB pro Mandant)."""
