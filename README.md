# wai

## Quickstart

1. **API-Key setzen** (in der Shell oder in `.env` neben der `docker-compose.yml`):
   ```bash
   export OPENAI_API_KEY=sk-...
   ```
2. **Stack starten** (führt Alembic-Migrationen für admin_db + logging_db aus und legt den Demo-Tenant an):
   ```bash
   ./scripts/start_local.sh
   ```
3. **Chat öffnen**: http://localhost:8500
4. **Logs anschauen**: `tail -f logs/gateway.log logs/mcp_mock.log`

### Weitere Tenants anlegen
```bash
docker compose exec gateway python scripts/create_tenant.py <slug>
# z.B.
docker compose exec gateway python scripts/create_tenant.py gaertnerei_mueller
# Auch erlaubt (wird transliteriert):
docker compose exec gateway python scripts/create_tenant.py "Gärtnerei Müller GmbH"
```

### Migrationen
```bash
# Admin/Logging einmalig
docker compose exec gateway alembic -c alembic-admin.ini upgrade head
docker compose exec gateway alembic -c alembic-logging.ini upgrade head
# Tenant pro Slug
docker compose exec gateway alembic -c alembic-tenant.ini -x tenant_slug=demo upgrade head
```

| Service | URL | Zweck |
|---|---|---|
| Chat-UI / Gateway | http://localhost:8500 | Demo-Chat, FastAPI-Docs unter `/docs` |
| Mock-MCP | http://localhost:8501 | Demo-Tool-Server (`/list_tools`, `/call_tool`) |
| pgAdmin | http://localhost:5550 | `admin@wai.local` / `wai_dev` |
| MinIO Console | http://localhost:9501 | `wai` / `wai_dev_minio` |
| Postgres | `localhost:5532` | User `wai`, Pass `wai_dev` |
| Redis | `localhost:6579` | — |

## Architektur (Demo-Stand)

```
Browser (HTML+JS Chat-UI)
    │  POST /chat {message, history}
    ▼
Gateway (FastAPI, :8500)
    │  delegiert an
    ▼
Manager-Agent  ──► OpenAI gpt-5.5 (Provider hardcoded)
    │
    │  bei Tool-Call (Function-Calling)
    ▼
Mock-MCP-Server (FastAPI, :8501)
    └── Tool: get_time
```

- **Provider** ist in `agents/manager/provider.py` hartkodiert (`gpt-5.5`). API-Key kommt aus `OPENAI_API_KEY`.
- **Manager** kann max. 1× Tool pro Turn aufrufen (single-round). Tool-Call läuft per HTTP an den Mock-MCP-Server, nicht über echtes MCP-Protokoll.
- **History** wird stateless im Frontend gehalten — keine DB-Persistenz in dieser Demo.
- **Logging** zentral via `lib/logging.py`, schreibt nach stdout + `logs/<service>.log`.

Detail-READMEs:
- [`agents/manager`](agents/manager/README.md) — Manager-Agent
- [`mcp_servers/mock_mcp`](mcp_servers/mock_mcp/README.md) — Mock-MCP-Server
- [`agents/`](agents/README.md), [`tools/`](tools/README.md) — Übersichten der weiteren Skelette

## Product-Value

## Folder
### /interface — Frontend (TBD: Angular/React)
### /gateway — FastAPI-Einstieg + Demo-Chat-UI
### /agents — Fach-Agents (mit Entscheidungs-Capability)
#### /agents/<agent>/ — z.B. `manager`, `coach`, `finance`, …
### /tools — deterministische Tools (MCP-Server)
#### /tools/<tool>/ — z.B. `database_management`, `embeddings_search`, …
### /mcp_servers — Mock-/Demo-MCP-Server für die Frühphase
### /lib — geteilter Python-Code (DB, Logging, MCP-Base, …)
### /scripts — lokale Dev-/Ops-Helper (start, init-db, …)

## databases
Es gibt **drei logische DB-Klassen**, jede mit eigener Alembic-Historie:

### admin_db (zentral, eine)
Plattform-Administration: `Tenant`, `UserData`, `TenantMembership`,
`TenantSettingsEntry`, `AiProvider`. Hier wohnen die Logins (sowohl Plattform-Staff
als auch Tenant-Mitarbeiter) und die Verbindung User ↔ Mandant.

### logging_db (zentral, eine)
Append-only Telemetrie: `RequestLog`, `EventLog`, `LogEntry`, `CronWorker`-Heartbeats.
Trägt `tenant_id` als Tag — Plattform-Support kann mandantenübergreifend suchen.

### tenant_&lt;slug&gt; (eine physische DB pro Mandant)
Alle fachlichen Daten des Kunden: `Project`, `Task`, `Note`, `Comment`, `Tag`,
`Attachment`, `Reminder`, `Account`, `Contact`, `Lead`, `Deal`, `Pipeline`, `Stage`,
`Interaction`, plus die Chat-Historie (`AiChat`, `AiMessage`, `AiToolCall`).
Neue Mandanten via `scripts/create_tenant.py` — physische DB + pgvector + Alembic.

**Bewusste Design-Entscheidung**: Es gibt **keine Foreign-Key-Constraints** in der DB.
Alle Beziehungen sind nackte Integer-IDs (`user_id`, `account_id`, …). Vorteile:
weniger Migrations-Schmerz, Cross-DB-Pointer (admin → tenant) sind möglich,
polymorphes Verlinken via `(target_cls, target_id)` ist trivial.

## Agents vs Tools
Agents haben 'descision' capability
Tools nicht, selbst wenn sie AI calls machen
Agents dealen mit unsicherheit/ambiguität
Tools liefern eine klare aktionsoberfläche
Agents un tools sind im grunde MCP server mit APIS.

## Rollen & Rechnte-Management
### Plattform-Roles VS tenant-roles

## SQL-Creation
- agenten können sql abfragen erstellen und die an das db tool senden

## FORM/View-Creation

## Logging/Debug/Visibility
- jeder tenant-db hat einen support user, der dann mehr sehen kann, 
  also so details usw. also die debug info - dort wo der normale nutzer
  nur den default output sieht

## Learning der Agenten

## Hearthbeat

## Agenten-Magie
- die meiste Abläufe muss man nicht mehr "coden", sondern als
  MD file festhalten.