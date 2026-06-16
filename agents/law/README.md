# law

**Typ:** Agent
**Status:** Skeleton

## Zweck
Juristische Themen: Vertrags-Analyse, Klauseln prüfen, Fristen identifizieren, Compliance-Checks. **Keine Rechtsberatung** — liefert Hinweise, der User entscheidet.

## Verantwortlichkeiten
- Verträge aus `minio` lesen, strukturieren
- Risiko-Klauseln markieren
- Fristen als `Reminder` anlegen
- Recherche in internen + externen Normen

## Genutzte Tools
- `tools/minio` — Vertrags-PDFs
- `tools/embeddings_search` — Norm-/Vertrags-Datenbank
- `tools/websearch` — externe Recherche
- `tools/database_management`

## DB-Zugriffe
- Tenant DB: `File`, `Norm`, `Reminder`

## MCP-Schnittstelle
TBD
