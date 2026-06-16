# coach

**Typ:** Agent
**Status:** Skeleton

## Zweck
Begleitet den User bei der Weiterentwicklung — fragt aktiv nach, gibt Feedback, schlägt Lernpfade vor. Kein reines Q&A, sondern proaktiv.

## Verantwortlichkeiten
- Skill-Profil des Users pflegen (`Skill`-Tabelle)
- Lernziele vorschlagen und nachhalten
- Fragen stellen statt nur Antworten geben
- Fortschritt visualisieren (über `visualizer`)

## Genutzte Tools
- `tools/database_management` — Skill-/Lernfortschritt
- `tools/embeddings_search` — passende Lerninhalte finden

## DB-Zugriffe
- Tenant DB: `User`, `Skill`, `Question`, `NoteItem`

## MCP-Schnittstelle
TBD
