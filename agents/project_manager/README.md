# project_manager

**Typ:** Agent
**Status:** Skeleton

## Zweck
Projekt-/Task-Management: Projekte anlegen, Tasks aufschlüsseln, Fortschritt nachhalten, Reminder setzen.

## Verantwortlichkeiten
- Projekt-Setup aus grober User-Beschreibung (Tasks vorschlagen)
- Abhängigkeiten zwischen Tasks erkennen
- Fortschritts-Reports
- Eskalation bei überfälligen Tasks

## Genutzte Tools
- `tools/tasks` — primäres Tool
- `tools/database_management`

## DB-Zugriffe
- Tenant DB: `Project`, `Task`, `Reminder`, `Comment`

## MCP-Schnittstelle
TBD
