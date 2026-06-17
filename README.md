# wai

## Quickstart

1. **API-Key setzen** (in der Shell oder in `.env` neben der `docker-compose.yml`):
   ```bash
   export OPENAI_API_KEY=sk-...
   ```
2. **Stack starten**:
   ```bash
   ./scripts/start_local.sh
   ```
3. **Chat öffnen**: http://localhost:8500
4. **Logs anschauen**: `tail -f logs/gateway.log logs/mcp_mock.log`

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
### Admin DB
Hier werden die Customers gepflegt -> unsere Customers; und ebenso unsere 
admin accounts. Zudem wird heir gefpegt welchen zugirff unsere kunden haben
usw. Also alles was nicht unsere kunden selbst eiunstellen können.

### Logging DB
hier landen events, die den kunden nicht interessieren, aber für uns als plattform
betreiber relevant sind um das ganze zu adminsitrieren und zu überwachen.

### Tenant DB 
Auf den Teannt dbs sind alle daten die dem kunden gehören.

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