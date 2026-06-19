"""Entities in tenant_<slug>.

Allgemeine fachliche Tabellen pro Mandant. Polymorph adressierbare
Entities registrieren sich beim Import ueber @register_entity (siehe
lib/polymorphic.py); Alembic-env.py importiert dieses Paket, damit
TenantBase.metadata alle Tabellen kennt.

Die CRM-Entitaeten liegen im Unterpaket lib.entities.tenant.crm und
werden hier re-exportiert.
"""
from lib.entities.tenant.ai_chat import AiChat
from lib.entities.tenant.ai_message import AiMessage
from lib.entities.tenant.ai_tool_call import AiToolCall
from lib.entities.tenant.attachment import Attachment
from lib.entities.tenant.chat_artifact import ChatArtifact
from lib.entities.tenant.comment import Comment
from lib.entities.tenant.crm import (
    Account,
    Contact,
    Deal,
    Interaction,
    Lead,
    Pipeline,
    Stage,
)
from lib.entities.tenant.note import Note
from lib.entities.tenant.project import Project
from lib.entities.tenant.reminder import Reminder
from lib.entities.tenant.tag import Tag
from lib.entities.tenant.tag_assignment import TagAssignment
from lib.entities.tenant.task import Task

__all__ = [
    "Account",
    "AiChat",
    "AiMessage",
    "AiToolCall",
    "Attachment",
    "ChatArtifact",
    "Comment",
    "Contact",
    "Deal",
    "Interaction",
    "Lead",
    "Note",
    "Pipeline",
    "Project",
    "Reminder",
    "Stage",
    "Tag",
    "TagAssignment",
    "Task",
]
