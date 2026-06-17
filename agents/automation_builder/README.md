# automation_builder

**Typ:** Agent
**Status:** Skeleton

## Zweck
Nimmt User-Intent ("immer wenn X passiert, mach Y") entgegen und erzeugt daraus eine ausführbare Automatisierung — als MD-/JSON-Workflow, der vom Runtime ausgeführt werden kann.

## Verantwortlichkeiten
- Intent klären (Rückfragen bei Ambiguität)
- Trigger + Bedingungen + Aktionen identifizieren
- Workflow-Definition generieren und im Tenant-Storage ablegen
- Vorschlag zur User-Freigabe vorlegen

## Genutzte Tools
- `tools/database_management` — Workflow-Definitionen persistieren
- `tools/tasks` — wenn Automatisierung Tasks anlegt

## DB-Zugriffe
- Tenant DB: `Automation`, `AutomationRun` (TBD in `DatabaseStructure.md`)

## MCP-Schnittstelle
TBD
