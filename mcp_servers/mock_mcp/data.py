"""Geteilte Mock-Daten für den Lead-Manager-Demo.

Wird vom MCP-Mock-Server (Quelle der Tool-Aufrufe) UND vom Gateway
(Demo-Schaufenster auf der Chat-UI) importiert, damit beide auf
derselben Stamm-DB arbeiten.
"""

KUNDEN_DB: dict[str, dict] = {
    "meier": {"projekt": "Dachsanierung", "status": "Wartet auf Material", "rechnung_offen": True, "notizen": []},
    "schmidt": {"projekt": "Heizungswartung", "status": "Abgeschlossen", "rechnung_offen": False, "notizen": []},
    "mueller": {"projekt": "Badrenovierung", "status": "In Arbeit", "rechnung_offen": True, "notizen": []},
}

TOOLS: list[dict] = [
    {
        "name": "hole_kunden_status",
        "beschreibung": "Schlägt einen Kunden namentlich nach und gibt Projekt, Status und offene Rechnung zurück.",
        "parameter": [{"name": "kunden_name", "typ": "string"}],
    },
    {
        "name": "erstelle_kunden_notiz",
        "beschreibung": "Hängt eine Notiz an einen Kunden an. Legt den Kunden bei Bedarf neu an.",
        "parameter": [
            {"name": "kunden_name", "typ": "string"},
            {"name": "notiz", "typ": "string"},
        ],
    },
    {
        "name": "suche_kunden",
        "beschreibung": "Sucht alle Kunden, deren Name den übergebenen Teilstring enthält.",
        "parameter": [{"name": "name_teil", "typ": "string"}],
    },
]

BEISPIEL_PROMPTS: list[str] = [
    "Was läuft beim Kunden Meier?",
    "Hat Schmidt noch eine offene Rechnung?",
    "Suche nach 'mu' in den Kundennamen.",
    "Notiere bei Mueller: 'Termin am Freitag bestätigt'.",
]
