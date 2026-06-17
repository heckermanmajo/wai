# hr

**Typ:** Agent
**Status:** Skeleton

## Zweck
Personalwesen: Mitarbeiter-Stammdaten, Urlaubsanträge, Onboarding-Checklisten, Skill-Matrix.

## Verantwortlichkeiten
- Mitarbeiter-Lifecycle (Eintritt, Wechsel, Austritt)
- Urlaubs-/Abwesenheits-Verwaltung
- Schulungs-/Skill-Tracking
- Datenschutz-konformes Logging (Sensitivitätsstufe beachten)

## Genutzte Tools
- `tools/database_management`
- `tools/tasks` — Onboarding-Tasks
- `tools/minio` — Verträge/Dokumente

## DB-Zugriffe
- Tenant DB: `User`, `TenantRole`, `Skill`, `File`

## MCP-Schnittstelle
TBD
