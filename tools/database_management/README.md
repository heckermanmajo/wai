# database_management

**Typ:** Tool
**Status:** Skeleton

## Zweck
Zentraler SQL-/DB-Zugang. Routet Queries an die richtige DB (Admin/Logging/Tenant), prüft Rechte, führt Statements aus, gibt strukturiertes Ergebnis zurück.

## API (Entwurf)
- `execute_sql(tenant_id, sql, params)` — read/write mit Whitelist
- `describe_schema(tenant_id)` — Tabellen/Spalten für SQL-erzeugende Agents
- `migrate(tenant_id, migration_id)` — kontrollierte Schema-Änderungen

## Sicherheit
- Parameterisierte Queries verpflichtend (CLAUDE.md → secure patterns)
- Role-Check pro Call (Plattform- vs. Tenant-Role)
- Support-User sieht Debug-Details (siehe Root-README → Logging/Debug/Visibility)
- DDL-Operationen brauchen explizite Bestätigung (CLAUDE.md → ddl-auto warning)

## Abhängigkeiten
- Postgres 16 (+ pgvector falls Embeddings-Felder)
- Connection-Pool aus `/lib/`
