# lib

**Status:** Skeleton (`agent.py` enthält bisher nur Stichpunkte).

## Zweck
Geteilter Code für Agents **und** Tools — DRY. Nichts hier darf Agent- oder Tool-spezifisch sein.

## Geplante Module
- `db/` — Connection-Pools, Tenant-DB-Routing, Migrations-Helper
- `logging/` — strukturiertes Logging in die Logging-DB, Korrelation per Request-ID
- `mcp/` — Basisklasse für MCP-Server (Registration, Health, Auth)
- `crud/` — generische CRUD-Helper über SQLAlchemy/Pydantic
- `auth/` — Role-Check (Plattform-Roles vs. Tenant-Roles)
- `events/` — `SystemEvent` / `WorldEvent` / `LoggingEvent` Publisher

## Konventionen
- Python 3.12+
- Typing strict (mypy/pyright)
- Keine Imports aus `/agents/` oder `/tools/` — Einbahnstraße: lib → agents/tools, nie zurück.
