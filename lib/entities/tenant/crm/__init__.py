"""CRM-Entitaeten pro Mandant.

Alle Klassen liegen in tenant_<slug> und sind ueber Aliase
"crm.*" polymorph adressierbar (siehe lib/polymorphic.py).

Lead und Contact sind bewusst getrennte Tabellen — ein Lead wird per
lead_convert() in einen Contact ueberfuehrt; Lead.converted_contact_id
fungiert dabei als nackte Bruecke ohne FK-Constraint.
"""
from lib.entities.tenant.crm.account import Account
from lib.entities.tenant.crm.contact import Contact
from lib.entities.tenant.crm.deal import Deal
from lib.entities.tenant.crm.interaction import Interaction
from lib.entities.tenant.crm.lead import Lead
from lib.entities.tenant.crm.pipeline import Pipeline
from lib.entities.tenant.crm.stage import Stage

__all__ = [
    "Account",
    "Contact",
    "Deal",
    "Interaction",
    "Lead",
    "Pipeline",
    "Stage",
]
