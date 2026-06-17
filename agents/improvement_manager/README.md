# improvement_manager

**Typ:** Agent
**Status:** Skeleton

## Zweck
Kontinuierlicher Verbesserungs-Prozess (KVP). Sammelt Probleme/Ideen, kategorisiert, priorisiert, schlägt Maßnahmen vor und begleitet die Umsetzung.

## Verantwortlichkeiten
- `Problem`-Einträge aufnehmen und clustern
- Root-Cause-Vorschläge generieren
- Maßnahmen in `Task`s umwandeln
- Wirkungs-Tracking nach Umsetzung

## Genutzte Tools
- `tools/database_management`
- `tools/tasks`
- `tools/embeddings_search` — ähnliche Probleme finden

## DB-Zugriffe
- Tenant DB: `Problem`, `Task`, `Norm`

## MCP-Schnittstelle
TBD
