# researcher

**Typ:** Agent
**Status:** Skeleton

## Zweck
Recherchiert Fragen — kombiniert interne Tenant-Daten (Embeddings) mit externer Web-Suche. Liefert zitierte, geprüfte Antworten.

## Verantwortlichkeiten
- Query in Sub-Fragen zerlegen
- Quellen sammeln (intern + extern)
- Aussagen adversarial gegenprüfen
- Synthese mit Quellenangaben

## Genutzte Tools
- `tools/embeddings_search`
- `tools/websearch`
- `tools/database_management` — Recherche-Ergebnisse als `NoteItem` ablegen

## DB-Zugriffe
- Tenant DB: `NoteItem`, `File`

## MCP-Schnittstelle
TBD
