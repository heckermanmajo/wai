# designer

**Typ:** Agent
**Status:** Skeleton

## Zweck
Entwirft Forms und Views für die Tenant-Oberfläche. Übersetzt fachliche Anforderungen ("ich brauch ein Formular für Reisekosten") in Form-/View-Definitionen, die das `/interface` rendert.

## Verantwortlichkeiten
- Felder, Validierungen, Layout vorschlagen
- Bestehende Forms wiederverwenden statt duplizieren
- Form-Definition versionieren

## Genutzte Tools
- `tools/database_management` — Form-Schemas persistieren
- `tools/embeddings_search` — ähnliche bestehende Forms finden (Wiederverwendung)

## DB-Zugriffe
- Tenant DB: `Form`

## MCP-Schnittstelle
TBD
