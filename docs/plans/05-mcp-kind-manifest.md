# Plan 05 — MCP-Kind im Manifest + Sub-Agent-MCP-Umbau

**Welle 2, Feature 5. Vision-Ref: §21 (MCP-Kind), §8 (Worker-Sichtbarkeit).**

## Ziel

Zwei zusammenhängende Schritte in einem Plan:

1. **Sub-Agents werden zu echten MCP-Servern** (Entscheidung: jetzt machen, nicht V2). Damit hat jeder Sub-Agent einen eigenen Prozess + SSE-Endpoint + Manifest und ist über dieselbe Schnittstelle adressierbar wie passive Tool-MCPs.
2. Jeder MCP-Server (passiv oder Sub-Agent) deklariert über ein `manifest`-Tool seine Rolle (`kind`). Damit kann:
   - Der Manager-Agent beim Tool-Call sofort entscheiden, ob er einen Sub-Chat anlegen muss.
   - Der Debug-View (Plan 06) MCPs sauber getrennt listen.
   - Künftige Quota-/Kostenrechnung pro `kind` tarifieren.

## Schnittweise — was NICHT reinkommt

- **Kein vollständiges Manifest** wie in §21 beschrieben (Tools-Schema mit JSON-Schema-Validierung, Abhängigkeiten, UI-Erweiterungen). Nur das `kind`-Feld + minimale Self-Description (`name`, `version`, `description`, `tools`-Liste).
- **Keine MCP-UI-Overlays** — kommt in Welle 6.
- **Keine MCP-Discovery zur Laufzeit** — statische Registry der Endpoints in `lib/agent.py` bleibt; nur Manifest wird remote gefetcht.
- **Keine Berechtigungs-Matrix** "MCP A darf MCP B aufrufen" — kommt mit Permissions-Iteration.
- **Nur `sales_support` wird in dieser Iteration tatsächlich umgebaut.** Die anderen 13 Sub-Agent-Verzeichnisse (`coach`, `designer`, `researcher`, …) sind heute leer/Stubs — sie folgen demselben Pattern, aber **eins nach dem anderen**, nicht alle in diesem Plan.
- **Kein `mixed`-Anwender** — `mixed` ist im Vokabular drin, aber kein Server nutzt es in V1.

## Datenmodell

**Keine DB-Änderung.** Das Manifest lebt im MCP-Server selbst als Tool-Response.

### Manifest-Format

Jeder MCP exponiert ein `manifest`-Tool:

```python
@mcp.tool()
def manifest() -> dict:
    return {
        "name": "wai-crm",
        "version": "0.1.0",
        "kind": "tool",                          # "tool" | "sub_agent" | "mixed"
        "description": "CRM-Operationen für Accounts, Contacts, Deals.",
        "tools": [
            {"name": "list_accounts", "kind": "function"},
            {"name": "create_contact", "kind": "function"},
            # bei mixed: pro Tool kind: "function" oder "sub_agent"
        ],
    }
```

`kind` auf MCP-Ebene gibt die Default-Klassifizierung. Bei `mixed` muss jedes Tool selbst `kind` deklarieren.

## Code-Touchpoints

### Schritt A — `manifest()`-Tool in den 3 existierenden MCPs

- `mcp_servers/crm_mcp/server.py` — `kind: "tool"`
- `mcp_servers/debug_mcp/server.py` — `kind: "tool"` (existiert schon `ping`-Tool, `manifest` dazu)
- `mcp_servers/mock_mcp/server.py` — `kind: "tool"`

### Schritt B — `sales_support` wird zu einem MCP-Server

**Architektonische Änderung.** Bisher:

- `agents/sales_support/agent.py` ist eine Python-Funktion `run_sales_support(task, ...) -> tuple[str, bool]`.
- Manager ruft sie direkt im selben Prozess via `from agents.sales_support.agent import run_sales_support`.
- Manager hat einen hartkodierten Sonderpfad `if name == "sales_support"` in `agents/manager/agent.py`.

Neu:

- Neues Verzeichnis `mcp_servers/sales_support_mcp/server.py` (oder: Sub-Agent-Server leben in `agents/sales_support/server.py` — siehe offene Frage unten). Empfehlung: **`agents/sales_support/server.py`**, damit Sub-Agent-Code zusammenhängend bleibt (Prompt + Logik + Server-Adapter im selben Verzeichnis).
- `FastMCP("wai-sales-support", host="0.0.0.0", port=8002)` (Port-Vergabe siehe `docker-compose.yml`).
- Ein Tool `sales_support(task: str) -> str` — dünner Wrapper, der intern `run_sales_support()` aufruft.
- Ein Tool `manifest() -> dict` mit `kind: "sub_agent"`.
- Bestehende `run_sales_support`-Funktion bleibt — sie wird vom Server gerufen, nicht mehr direkt vom Manager.

### Schritt C — Sub-Agent-MCP-Pattern dokumentieren

Damit die 13 noch leeren Sub-Agent-Verzeichnisse demselben Schnitt folgen:

- `agents/README.md` erweitern um den Sub-Agent-MCP-Pattern-Abschnitt (Boilerplate `server.py` mit `manifest()` + Tool, Port-Konvention, Docker-Service-Konvention).
- Ein Template-File `agents/_template/server.py` mit Platzhaltern, das beim Anlegen eines neuen Sub-Agents kopiert wird.

### Schritt D — `lib/agent.py` — Discovery + Routing

```python
# lib/agent.py

MCP_ENDPOINTS: list[tuple[str, str]] = [
    # (logischer Name, SSE-URL)
    ("crm", "http://crm-mcp:8001/sse"),
    ("debug", "http://debug-mcp:8001/sse"),
    ("mock", "http://mock-mcp:8001/sse"),
    ("sales_support", "http://sales-support:8002/sse"),
    # weitere Sub-Agents folgen
]

_MANIFEST_CACHE: dict[str, tuple[float, dict]] = {}  # url -> (expires_at, manifest)
_CACHE_TTL_SECONDS = 60

async def fetch_manifest(url: str) -> dict:
    """Fetcht manifest()-Tool von einem MCP, mit 60s-Cache."""

async def list_all_capabilities() -> dict:
    """Discoveryt alle MCP_ENDPOINTS, liefert dict {name: manifest}."""

async def lookup_tool_kind(tool_name: str) -> str:
    """Liefert 'function' | 'sub_agent' anhand der gemergten Manifeste."""
```

Sub-Agent-Registry (`SUB_AGENT_REGISTRY` in `agents/__init__.py`) **wird entfernt**, weil die Information jetzt aus dem Manifest des jeweiligen Servers kommt.

### Schritt E — `agents/manager/agent.py` — Routing nach `kind`

Heute: hartkodierte Unterscheidung `if name == "sales_support"` (Zeilen ~186, ~322, ~382). Ersetzen durch:

```python
tool_kind = await lookup_tool_kind(name)  # aus Manifest-Cache
if tool_kind == "sub_agent":
    # Sub-Chat anlegen, Lifecycle-Events emittieren (Plan 02)
    return await invoke_sub_agent_via_mcp(name, task, emitter=emitter, ...)
else:
    return await call_mcp_tool(name, args, ...)
```

`invoke_sub_agent_via_mcp` bündelt die bisherige `emit_sub_agent_call(...) + run_sales_support(...)`-Logik, aber statt direktem Python-Call macht sie einen MCP-Tool-Call zum jeweiligen Sub-Agent-Server.

Damit ist Sales-Support nicht mehr Sonderfall im Code — und der nächste Sub-Agent (Researcher etc.) braucht keine Manager-Code-Änderung, nur einen neuen Eintrag in `MCP_ENDPOINTS`.

### Schritt F — `docker-compose.yml`

Neuer Service:

```yaml
sales-support:
  build: { context: ., dockerfile: agents/sales_support/Dockerfile }
  ports: ["8002:8002"]
  environment: [...gleiche env wie crm-mcp...]
  depends_on: [postgres]
```

`agents/sales_support/Dockerfile` (neu) — vermutlich derselbe Base-Image wie `mcp_servers/crm_mcp/Dockerfile`. Wenn ein Pattern existiert (Build-Args), wiederverwenden.

## UI-Punkte

Keine direkt — alles wird im Debug-View (Plan 06) sichtbar.

## Tests

- `manifest`-Tool jedes MCP liefert valide Struktur (4 MCPs jetzt: crm, debug, mock, sales_support).
- `fetch_manifest` cached korrekt (zweiter Call innerhalb 60s = kein Round-Trip).
- `list_all_capabilities` macht Round-Trip zu allen MCPs und mergt Antworten.
- Manager-Agent ruft mit `kind="sub_agent"` den richtigen Code-Pfad und emittiert `sub_agent_started/completed` (verlässt sich auf Plan 02).
- Manager-Agent mit `kind="function"` läuft den MCP-Tool-Pfad.
- Lifecycle: sales-support-Container startet sauber, Tool-Call vom Manager landet erfolgreich.

## Offene Fragen

- **Wo lebt der Sub-Agent-Server-Code — `mcp_servers/sales_support_mcp/server.py` oder `agents/sales_support/server.py`?** → Empfehlung: **`agents/sales_support/server.py`**, damit Prompt + Logik + Server-Adapter zusammenhängend bleiben und `mcp_servers/` nur passive Tool-MCPs hält. Wenn doch eine harte Trennung gewünscht ist, müssen wir das vor dem Umbau klären.
- **Port-Vergabe** — heute haben crm/debug/mock alle `8001` intern. Im docker-compose werden sie über Service-Namen unterschieden. Für sales-support: gleiches Pattern, intern `8001`, Service-Name `sales-support`? Oder durchnummeriert `8001`, `8002`, …? → Vorschlag: intern bleibt jeder bei `8001`, Service-Name diskriminiert. Konsistenter.
- **MCP-Discovery-Robustheit** — wenn ein Sub-Agent-MCP offline ist, soll `list_all_capabilities` einen Eintrag mit `"status": "offline"` liefern statt zu werfen. Wichtig für Debug-View. Ist im Plan implizit, hier explizit notiert.
- **Wann werden die 13 leeren Sub-Agents (`coach`, `researcher`, …) umgebaut?** → Nicht in diesem Plan. Sie sind heute Stubs; sobald einer fachlich befüllt wird, kriegt er beim Anlegen direkt das MCP-Server-Skelett (siehe Schritt C).
- **`mixed`-Kind in V1?** → entschieden: **im Vokabular drin, kein konkreter Anwender**. Code-Pfad existiert, niemand nutzt ihn — Vorausschau ohne Schulden.

## Aufwand

- `manifest`-Tool in 3 existierenden MCPs: 30 min
- Sub-Agent-MCP-Server für `sales_support` (Boilerplate FastMCP + Tool-Wrapper + manifest): 2.5h
- Dockerfile + docker-compose-Service: 1h
- Sub-Agent-MCP-Pattern dokumentieren + Template-File: 1h
- Discovery-Helper (`fetch_manifest`, `list_all_capabilities`, `lookup_tool_kind`) mit 60s-Cache: 1.5h
- Manager-Routing-Refactor (drei Touch-Stellen, `SUB_AGENT_REGISTRY` weg, einheitliches Routing): 2h
- Integration-Test (Container hoch, sales-support-Call durchgehen): 1.5h
- Unit-Tests: 1.5h

**Gesamt: ~11h.** Deutlich größer als die ursprünglichen ~4h, weil der Sub-Agent-MCP-Umbau ein eigener Prozess samt Container-Lifecycle ist. Wert dafür: Architektur passt ab sofort zur Vision §21, kein zweites Refactor später.

## Abhängigkeiten

- **Plan 02** (Sub-Agent-Lifecycle-Events) — **hart**, weil das Routing-Refactor in Schritt E die Lifecycle-Events sauber emittieren muss. Plan 02 muss vor Plan 05 fertig sein, sonst wird der Refactor unsauber.
- **Plan 01** (Trace-Context) — weich, hilft beim Cross-Process-Trace-Forwarding (Manager → Sub-Agent-MCP).
- **Plan 06** (Debug-View) — wird durch diesen Plan möglich gemacht (`list_all_capabilities` als Datenbasis für den MCPs-Tab).

## Umgesetzt am 2026-06-20

- `manifest()`-Tool in den drei existierenden MCPs ergänzt (`crm_mcp`, `debug_mcp`, `mock_mcp`) — jeweils mit `kind: "tool"` und Tool-Liste pro Server.
- Sub-Agent-MCP-Server für `sales_support`: `agents/sales_support/server.py` mit `FastMCP("wai-sales-support")`, Tools `manifest()` und `sales_support(task, tenant_slug, sub_trace_uid, sub_chat_id, user_id)`. Dünner Wrapper, der die bestehende `run_sales_support`-Logik aus `agents/sales_support/agent.py` aufruft.
- Docker-Compose: neuer Service `sales_support` (extern Port `8504`, intern `8001`, gleiches Base-Image wie Manager/MCPs, dazu `MCP_CRM_URL` als Dependency).
- `lib/agent.py` erweitert um Discovery-Helper:
  - `MCP_ENDPOINTS` (statische Registry mit `crm`, `debug`, `mock`, `sales_support`).
  - `fetch_manifest(url)` mit 60s-Cache, robustes Offline-Fallback (`status="offline"`).
  - `list_all_capabilities()` (parallel via `asyncio.gather`).
  - `lookup_tool_kind(tool_name)` → `"function" | "sub_agent" | "mixed"`.
  - `find_endpoint_for_tool(tool_name)` für den Routing-Pfad.
  - `_call_sub_agent_via_mcp(...)` + `invoke_sub_agent_via_mcp(...)` — wickelt MCP-Tool-Call in die existierende `emit_sub_agent_call`-Klammer (Sub-Trace, Sub-Chat, Lifecycle-Events).
- `agents/manager/agent.py` refaktoriert:
  - Hartcodiertes `if name == "sales_support"` entfernt; `_dispatch_tool_call` entscheidet nun ausschließlich über `lookup_tool_kind`.
  - `SALES_SUPPORT_TOOL` heisst jetzt `SUB_AGENT_TOOL_FALLBACKS` und dient nur als Discovery-Fallback.
  - Tool-Liste im `_run_tool_loop` wird via `_discover_sub_agent_tools()` aus den Manifesten zusammengesetzt — jeder weitere Sub-Agent erscheint automatisch, sobald sein MCP-Endpoint in `MCP_ENDPOINTS` steht.
  - Direkte `run_sales_support`-Import entfernt; Sub-Agent-Logik läuft jetzt über MCP-Tool-Call.
- Pattern-Doku: `agents/README.md` um den "Sub-Agent-MCP-Pattern"-Abschnitt (4-Punkt-Boilerplate, Port-Konvention `8501–8504`, nächster frei ab `8505`).
- Template: `agents/_template/server.py` (+ leeres `__init__.py`) als Kopier-Vorlage für neue Sub-Agents.
- Kein `SUB_AGENT_REGISTRY` in `agents/__init__.py` — die Datei war ohnehin leer, Plan 05 sah die Registry über das Manifest ohnehin vor.
