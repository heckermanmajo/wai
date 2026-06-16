# tippse

**Typ:** Agent
**Status:** Skeleton

## Zweck
Schnelle Erfassung — Diktat, Notizen, Memos. Wandelt unstrukturierten Input (Sprache/Text) in strukturierte Einträge (`NoteItem`, `Task`, `Reminder`, `Message`).

## Verantwortlichkeiten
- Transkription (falls Audio-Input)
- Intent-Erkennung: Notiz vs. Task vs. Reminder vs. Mail
- Richtigen Zielspeicher wählen
- Rückbestätigung an User

## Genutzte Tools
- `tools/database_management`
- `tools/tasks`
- ggf. externes Audio-Modell (siehe CLAUDE.md → audio defaults)

## DB-Zugriffe
- Tenant DB: `NoteItem`, `Task`, `Reminder`, `Message`

## MCP-Schnittstelle
TBD
