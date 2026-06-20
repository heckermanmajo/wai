"""Statische Action-Registry — wird beim Import von lib.actions geladen.

Jede register_action(...)-Aufruf taegt sich in _REGISTRY in lib.actions ein.
Neue Aktionen einfach hier ergaenzen; LLM-Refinement (lib/actions_refine.py)
darf zusaetzlich dynamische Aktionen erzeugen, statische bleiben aber
das Rueckgrat.

Kategorien (Konvention):
    analyze      — Zusammenfassung, Extraktion, Klassifizierung
    transform    — Uebersetzung, Format-Wechsel, Umformulierung
    communicate  — E-Mail, Nachricht, Termin
    create       — Neue Resource anlegen
    link         — Verknuepfen / Pinnen / Taggen
    archive      — Loeschen, Archivieren
    general      — Sonstiges
"""
from __future__ import annotations

from lib.actions import Action, ActionExecution, register_action


# ---------------------------------------------------------------------------
# Documents (core.document)
# ---------------------------------------------------------------------------

register_action(Action(
    key="doc.summarize",
    label="Zusammenfassen",
    description="Erzeugt eine 3-5 Bullet-Zusammenfassung des Dokuments.",
    icon="📝",
    category="analyze",
    resource_types=["core.document"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Fasse das Dokument #{resource.id} ({resource.title}) in 3-5 "
            "Bulletpoints zusammen. Nutze document_get, wenn du den vollen "
            "Inhalt brauchst."
        ),
    ),
))

register_action(Action(
    key="doc.extract_actions",
    label="Action-Items extrahieren",
    description="Findet alle TODO/Action-Items im Dokument und listet sie.",
    icon="✅",
    category="analyze",
    resource_types=["core.document"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Lies Dokument #{resource.id} ({resource.title}) via document_get und "
            "extrahiere alle Action-Items / TODOs als Liste. Optional: lege "
            "passende Tasks an."
        ),
    ),
))

register_action(Action(
    key="doc.translate_en",
    label="Auf Englisch",
    description="Uebersetzt den Inhalt ins Englische und legt eine neue Document-Version an.",
    icon="🌐",
    category="transform",
    resource_types=["core.document"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Uebersetze Dokument #{resource.id} ({resource.title}) ins Englische. "
            "Lade es mit document_get, schreibe die Uebersetzung als neuen "
            "Markdown-Inhalt und speichere mit document_edit (id={resource.id})."
        ),
    ),
))

register_action(Action(
    key="doc.tighten",
    label="Knapper machen",
    description="Kuerzt und straft den Text, ohne Inhalt zu verlieren.",
    icon="✂️",
    category="transform",
    resource_types=["core.document"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Ueberarbeite Dokument #{resource.id} so, dass es ~30 Prozent kuerzer "
            "wird ohne wesentliche Information zu verlieren. Speichere als "
            "neue Version via document_edit."
        ),
    ),
))

register_action(Action(
    key="doc.outline",
    label="Outline erstellen",
    description="Generiert eine hierarchische Gliederung des Dokuments.",
    icon="🗂️",
    category="analyze",
    resource_types=["core.document"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Erstelle eine hierarchische Outline (H1/H2/H3) zu Dokument "
            "#{resource.id} ({resource.title}). Nutze document_get."
        ),
    ),
))

register_action(Action(
    key="doc.delete",
    label="Loeschen",
    description="Soft-Delete des Dokuments.",
    icon="🗑️",
    category="archive",
    resource_types=["core.document"],
    needs_confirmation=True,
    is_destructive=True,
    execution=ActionExecution(
        kind="tool_call",
        tool_name="document_delete",
        args={"id": "{resource.id}"},
    ),
))


# ---------------------------------------------------------------------------
# Notes (core.note)
# ---------------------------------------------------------------------------

register_action(Action(
    key="note.to_document",
    label="In Dokument ueberfuehren",
    description="Macht aus dieser Notiz ein eigenstaendiges Document.",
    icon="📄",
    category="transform",
    resource_types=["core.note"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Erstelle ein neues Document via document_create aus dem Inhalt der "
            "Note #{resource.id} ({resource.title|Notiz}). Behalte den Titel falls "
            "gesetzt, sonst leite einen sinnvollen Titel ab."
        ),
    ),
))

register_action(Action(
    key="note.expand",
    label="Ausformulieren",
    description="Macht aus Stichpunkten/Notes einen ausformulierten Fliesstext.",
    icon="✍️",
    category="transform",
    resource_types=["core.note"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Formuliere die Note #{resource.id} zu einem zusammenhaengenden "
            "Text aus. Lege das Ergebnis als neues Document an."
        ),
    ),
))


# ---------------------------------------------------------------------------
# Tasks (core.task)
# ---------------------------------------------------------------------------

register_action(Action(
    key="task.next_step",
    label="Naechster Schritt",
    description="Was ist konkret als naechstes zu tun?",
    icon="➡️",
    category="analyze",
    resource_types=["core.task"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Schlage fuer Task #{resource.id} ({resource.title}) den konkret "
            "naechsten Schritt vor — eine handhabbare Subaufgabe, kein "
            "Generikum."
        ),
    ),
))


# ---------------------------------------------------------------------------
# CRM Contacts (crm.contact)
# ---------------------------------------------------------------------------

register_action(Action(
    key="contact.draft_email",
    label="E-Mail entwerfen",
    description="Entwirft eine E-Mail-Vorlage an diesen Kontakt.",
    icon="📧",
    category="communicate",
    resource_types=["crm.contact"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Entwirf eine kurze E-Mail an Kontakt #{resource.id} "
            "({resource.first_name} {resource.last_name}). Frag nach, "
            "welcher Anlass — falls noch unklar."
        ),
    ),
))

register_action(Action(
    key="contact.related",
    label="Verwandtes anzeigen",
    description="Listet Leads, Deals, Notes und Termine zu diesem Kontakt.",
    icon="🔗",
    category="analyze",
    resource_types=["crm.contact"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Zeige alles was wir zu Kontakt #{resource.id} "
            "({resource.first_name} {resource.last_name}) haben — Leads, Deals, "
            "Notes, letzte Interactions. Strukturiert."
        ),
    ),
))


# ---------------------------------------------------------------------------
# CRM Deals (crm.deal)
# ---------------------------------------------------------------------------

register_action(Action(
    key="deal.next_action",
    label="Naechste Aktion festlegen",
    description="Was ist der naechste konkrete Schritt, um den Deal voranzubringen?",
    icon="🎯",
    category="analyze",
    resource_types=["crm.deal"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Analysiere Deal #{resource.id} und schlage die naechste konkrete "
            "Aktion vor — inklusive Termin/Frist."
        ),
    ),
))

register_action(Action(
    key="deal.advance_stage",
    label="Stage weiterschalten",
    description="Schiebt den Deal in die naechste Stage seiner Pipeline.",
    icon="⏩",
    category="transform",
    resource_types=["crm.deal"],
    needs_confirmation=True,
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Schalte Deal #{resource.id} in die naechste Stage. Pruefe vorher "
            "via pipeline_list, welche Stages es gibt."
        ),
    ),
))


# ---------------------------------------------------------------------------
# CRM Leads (crm.lead)
# ---------------------------------------------------------------------------

register_action(Action(
    key="lead.qualify",
    label="Qualifizieren",
    description="Fasst alle bekannten Infos zusammen, bewertet Reife und Lead-Score.",
    icon="🎚️",
    category="analyze",
    resource_types=["crm.lead"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Qualifiziere Lead #{resource.id} ({resource.first_name} "
            "{resource.last_name}). Wie gut passt das Profil? Was fehlt fuer "
            "die Conversion?"
        ),
    ),
))

register_action(Action(
    key="lead.convert",
    label="In Deal konvertieren",
    description="Macht aus dem Lead einen Deal.",
    icon="🔁",
    category="transform",
    resource_types=["crm.lead"],
    needs_confirmation=True,
    execution=ActionExecution(
        kind="tool_call",
        tool_name="lead_convert",
        args={"lead_id": "{resource.id}"},
    ),
))


# ---------------------------------------------------------------------------
# AiChat (ai.chat)
# ---------------------------------------------------------------------------

register_action(Action(
    key="chat.summarize",
    label="Chat zusammenfassen",
    description="Was ist im Chat passiert? Welche Entscheidungen wurden getroffen?",
    icon="📋",
    category="analyze",
    resource_types=["ai.chat"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Fasse den Chat #{resource.id} zusammen. Welche Themen, "
            "Entscheidungen, offene Fragen?"
        ),
    ),
))

register_action(Action(
    key="chat.to_document",
    label="In Dokument ueberfuehren",
    description="Speichert die wichtigsten Erkenntnisse des Chats als Document.",
    icon="📄",
    category="transform",
    resource_types=["ai.chat"],
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Extrahiere die wichtigen Ergebnisse aus Chat #{resource.id} und "
            "lege sie als Document an (document_create). Titel orientiert sich "
            "am Hauptthema."
        ),
    ),
))


# ---------------------------------------------------------------------------
# Globale Aktionen (keine resource_types)
# ---------------------------------------------------------------------------

register_action(Action(
    key="global.new_document",
    label="Neues Dokument",
    description="Startet einen Chat, der ein neues Document anlegt.",
    icon="📄",
    category="create",
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Lege ein neues Document an. Frag mich kurz nach Titel und Zweck, "
            "schlage dann eine Outline vor."
        ),
    ),
))

register_action(Action(
    key="global.daily_summary",
    label="Tages-Summary",
    description="Was wurde heute getan, was steht an?",
    icon="📅",
    category="analyze",
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Erstelle eine kurze Tages-Summary: Was wurde heute angelegt/geaendert "
            "(Documents, Tasks, Deals), was steht an (offene Tasks, naechste Termine)?"
        ),
    ),
))

register_action(Action(
    key="global.new_lead",
    label="Neuer Lead",
    description="Erfasst einen neuen Lead per Konversation.",
    icon="🆕",
    category="create",
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Lege einen neuen Lead an. Frag mich nach Name, Firma, Quelle und "
            "Kontext, dann nutze lead_create."
        ),
    ),
))

register_action(Action(
    key="global.search_semantic",
    label="Semantische Suche",
    description="Suche nach Inhalt quer durch Documents/Notes/Tasks.",
    icon="🔍",
    category="general",
    execution=ActionExecution(
        kind="chat_task",
        prompt_template=(
            "Ich suche nach… (Stichwort gib ich dir): nutze semantic_search "
            "und zeig mir die top 5 Treffer mit Kurzkontext."
        ),
    ),
))
