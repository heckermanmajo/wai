# mock_mcp

**Typ:** Mock-MCP-Server (HTTP-Stub)
**Status:** Demo / starting point

## Zweck
Stub-Server für die Früh-Phase: exponiert ein Dummy-Tool (`get_time`) über HTTP-Endpoints im MCP-Stil, damit der `manager`-Agent gegen ein "externes" Tool kommunizieren kann — ohne dass schon echte MCP-Infrastruktur steht.

## Endpoints
| Method | Path | Beschreibung |
|---|---|---|
| GET  | `/health`     | Liveness |
| GET  | `/list_tools` | Tool-Manifest |
| POST | `/call_tool`  | `{name, arguments}` → `{result}` |

## Tools
| Name | Beschreibung |
|---|---|
| `get_time` | Liefert aktuelle UTC-Zeit als ISO-8601-String |

## Lokal aufrufen
```bash
curl http://localhost:8501/list_tools
curl -X POST http://localhost:8501/call_tool \
  -H 'Content-Type: application/json' \
  -d '{"name":"get_time","arguments":{}}'
```

## Run
Service `mcp_mock` in `docker-compose.yml` auf Port `:8501`. Nutzt das gleiche Image wie der Gateway (anderer `command`).
