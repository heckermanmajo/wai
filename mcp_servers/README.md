# mcp_servers

Sammelt **Mock-/Demo-MCP-Server** für die Frühphase. Echte produktive Tool-MCP-Server leben unter `/tools/`.

## Aktuelle Mocks
| Service | Beschreibung |
|---|---|
| `mock_mcp` | HTTP-Stub mit einem Dummy-Tool (`get_time`); wird vom `manager`-Agent als Function-Call-Ziel verwendet. |

## Konvention
- Jeder Mock-Server hat eigenes Image-Verzeichnis und eigenes `README.md`.
- Mocks nutzen **HTTP statt echtem MCP-Protokoll** — als Startpunkt einfacher zu bauen und zu debuggen.
- Bei Reifung migrieren wir das jeweilige Konzept nach `/tools/<name>/` und entfernen den Mock.
