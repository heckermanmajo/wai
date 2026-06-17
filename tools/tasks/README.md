# tasks

**Typ:** Tool
**Status:** Skeleton

## Zweck
CRUD + Trigger-Logik für `Task` und `Reminder`. Wird von vielen Agents genutzt, deshalb eigener Tool-Layer (DRY).

## API (Entwurf)
- `create(tenant_id, task)` — neu
- `update(tenant_id, task_id, patch)`
- `complete(tenant_id, task_id)`
- `list(tenant_id, filter)` — by user/project/status/due
- `set_reminder(tenant_id, task_id, when)` — koppelt `Reminder`

## Hooks
- Beim Anlegen/Update: SystemEvent in Logging-DB
- Bei Fälligkeit: Trigger an `manager`-Agent (Eskalations-Entscheidung dort)

## Abhängigkeiten
- `database_management`
- Scheduler (Redis-basiert) für Reminder-Fälligkeit
