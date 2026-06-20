# Agents

Verzeichnis aller Agent-Implementierungen. Jeder Unterordner ist ein eigenständiger Agent, exponiert als MCP-Server.

## Definition
Agents haben **Entscheidungs-Capability** und gehen mit Unsicherheit/Ambiguität um. Sie können Tools aufrufen, SQL erzeugen, Forms/Views vorschlagen — und delegieren deterministische Arbeit an `/tools/`.

Abgrenzung zu Tools: siehe Root-`README.md` → "Agents vs Tools".

## Aktuelle Agents
| Agent | Domäne |
|---|---|
| `automation_builder` | erzeugt Automatisierungs-Workflows aus User-Intent |
| `coach` | begleitet/bildet User weiter, fragt aktiv nach |
| `designer` | entwirft UI/Forms/Views |
| `finance` | Buchhaltung, Rechnungen, Reports |
| `hr` | Personal, Mitarbeiterverwaltung |
| `improvement_manager` | KVP, Prozessverbesserung |
| `law` | juristische Fragen, Vertragsanalyse |
| `manager` | Top-Level-Orchestrator, delegiert an Fach-Agents |
| `project_manager` | Projekte, Tasks, Reminders |
| `researcher` | Recherche (intern + web) |
| `sales_support` | Vertriebsunterstützung, Lead-Aufbereitung |
| `sm_agent` | Scrum-Master (TBD — Bedeutung bestätigen) |
| `tech_suuport` | Tech-Support **(Typo im Ordnernamen → `tech_support`)** |
| `tippse` | Notiz/Diktat/Schnellerfassung |
| `visualizer` | Charts, Diagramme, Visualisierungen |

## Konventionen
- Jeder Agent hat eigenes `README.md`, eigene MCP-Server-Definition, eigene Prompt-/Policy-MD-Files.
- Geteilter Code (DB-Connect, Logging, CRUD) kommt aus `/lib/`.
- Agent-Logik primär als **MD-Files** festhalten (siehe Root-README → "Agenten-Magie").

## Sub-Agent-MCP-Pattern (Plan 05)

Ein Sub-Agent **ist** ein MCP-Server mit `kind: "sub_agent"`. Damit ist er
über dieselbe SSE-/Manifest-Schnittstelle adressierbar wie ein passiver
Tool-MCP, und der Manager braucht keinen Sonderpfad mehr.

Boilerplate pro Sub-Agent:
1. `agents/<role>/agent.py` — `async def run_<role>(task, *, sub_emitter, sub_trace_uid, sub_chat_id, tenant_slug, user_id) -> str`. Hier lebt die fachliche Logik.
2. `agents/<role>/server.py` — FastMCP-Server. Zwei Tools: `manifest()` und ein `<role>()` als dünner Wrapper, der `run_<role>` aufruft. Template: `agents/_template/server.py`.
3. `docker-compose.yml` — neuen Service `<role>:` mit `command: ["python", "-m", "agents.<role>.server"]`, intern Port `8001`, extern frei (Konvention: `850N:8001`).
4. `lib/agent.MCP_ENDPOINTS` — neuen Eintrag `("<role>", "http://<role>:8001/sse")` hinzufügen.

Damit ist der Manager-Code nicht zu ändern — das `manifest()`-Tool deklariert
`kind: "sub_agent"`, `lookup_tool_kind()` greift den Kind ab, und
`_dispatch_tool_call` routet den Aufruf via `invoke_sub_agent_via_mcp`.

### Port-Vergabe (Konvention)
Intern bleibt jeder MCP-Container auf `:8001`. Extern (host-side) zaehlen
wir durch: `8501` (mock), `8502` (crm), `8503` (debug), `8504` (sales_support),
nächster freier ab `8505`. Der Service-Name im Docker-Netzwerk diskriminiert.
