"""Entities in admin_db.

Beim Import dieses Pakets werden alle Modelle registriert (an
AdminBase.metadata gehaengt). Alembic-env.py importiert dieses Paket,
damit die Migrationen die Tabellen sehen.
"""
from lib.entities.admin.ai_provider import AiProvider
from lib.entities.admin.membership import TenantMembership
from lib.entities.admin.settings import TenantSettingsEntry
from lib.entities.admin.tenant import Tenant
from lib.entities.admin.user import UserData

__all__ = [
    "AiProvider",
    "Tenant",
    "TenantMembership",
    "TenantSettingsEntry",
    "UserData",
]
