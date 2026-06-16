# manager

**Typ:** Agent (Orchestrator)
**Status:** Skeleton

## Zweck
Top-Level-Einstiegspunkt für User-Requests, wenn nicht eindeutig ist welcher Fach-Agent zuständig ist. Routet, delegiert, fasst Ergebnisse zusammen.

## Verantwortlichkeiten
- Request-Klassifikation → richtiger Fach-Agent
- Multi-Agent-Workflows koordinieren
- Konflikt-Resolution wenn mehrere Agents widersprüchliche Vorschläge liefern
- Gesamtkontext halten (über mehrere Agent-Calls hinweg)

## Genutzte Tools
- alle Fach-Agents (via MCP)
- `tools/database_management` — Chat-/Message-Historie

## DB-Zugriffe
- Tenant DB: `Chat`, `Message`, `User`

## MCP-Schnittstelle
TBD
