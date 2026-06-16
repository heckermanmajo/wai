# tech_support (Ordner-Typo: `tech_suuport`)

**Typ:** Agent
**Status:** Skeleton

> **Hinweis:** Ordnername hat einen Tippfehler (`tech_suuport` → `tech_support`). Korrektur via `git mv agents/tech_suuport agents/tech_support`.

## Zweck
Technischer Support für Tenant-User. First-Level-Antworten aus Dokumentation, Eskalation bei komplexen Themen.

## Verantwortlichkeiten
- Bekannte Probleme aus Wissensbasis beantworten
- Logs/SystemEvents auswerten wenn User-Problem reproduzierbar
- Ticket-Verwaltung
- Eskalation an Plattform-Support (mit Support-User-Zugriff auf Tenant-DB)

## Genutzte Tools
- `tools/embeddings_search` — Wissensbasis
- `tools/database_management`
- `tools/tasks`

## DB-Zugriffe
- Tenant DB: `Problem`, `Task`, `Message`
- Logging DB (read) — bei eskalierten Fällen

## MCP-Schnittstelle
TBD
