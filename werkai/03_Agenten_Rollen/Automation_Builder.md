# 🤖 Automation-Builder-Agent (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der Automation-Builder-Agent ist ein Spezial-Agent, der auf Basis von formuliertem User-Intent (z.B. *"Verbinde Baserow mit meinem Kalender, wenn ein neuer Bewerber eintrifft"*) eigenständig Automatisierungs-Workflows entwirft und konfiguriert.

## 2. Aufgaben & Fähigkeiten
- **Workflow-Design**: Analyse des Ziels und Übersetzung in logische API-Schritte.
- **Workflow-Generierung**: Generierung von JSON-Schemas für n8n-Workflows oder Make-Ketten.
- **Validierung**: Überprüfung der JSON-Strukturen auf Validität.

## 3. Tooling & Integrationen
- **n8n API**: Verbindung zur self-hosted n8n API zur automatischen Installation oder Deaktivierung von Workflows.
- **Datenbank**: Speicherung der Workflow-Kataloge und Vorlagen in PostgreSQL.
- **Testing**: Terminal-Schnittstellen zur Durchführung einfacher Testläufe.
