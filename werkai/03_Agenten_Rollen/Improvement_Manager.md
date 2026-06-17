# 🤖 Improvement-Manager (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der Improvement-Manager ist für die Qualitätssicherung und den kontinuierlichen Verbesserungsprozess (KVP) der gesamten Agenten-Plattform zuständig. 

## 2. Aufgaben & Fähigkeiten
- **Chatverlauf-Analyse**: Nachträgliche, asynchrone Analyse von Kundenchats und internen Agenten-Interaktionen.
- **Fehler-Erkennung**: Identifikation von Fehlklassifikationen, unvollständigen Antworten oder Systemhängern.
- **Prozess-Optimierung**: Vorschlag konkreter Verbesserungen (z.B. neue Prompts, zusätzliche Validierungsregeln in [[05_Coding_Guidelines|Coding Guidelines]] oder veränderte Workflows).

## 3. Tooling & Integrationen
- **Logging-DB**: Auswerten von Systemevents und Konversationslogs aus der PostgreSQL-Logging-Datenbank.
- **LLM-Nutzung**: Tier 1/Tier 2 asynchrone Batch-Prozesse zur Erkennung von Optimierungspotenzialen.
- **Speicherung**: Erstellung von Problemberichten und Verbesserungsvorschlägen in Baserow/PostgreSQL.
