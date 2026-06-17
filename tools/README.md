# Tools

Verzeichnis aller Tool-Implementierungen. Jeder Unterordner ist ein deterministisches Tool, exponiert als MCP-Server.

## Definition
Tools haben **keine Entscheidungs-Capability** — selbst wenn sie intern AI-Calls machen, liefern sie eine klare, vorhersagbare Aktionsoberfläche. Mehrdeutigkeit wird zurück an den aufrufenden Agent gegeben, nicht selbst aufgelöst.

Abgrenzung zu Agents: siehe Root-`README.md` → "Agents vs Tools".

## Aktuelle Tools
| Tool | Aufgabe |
|---|---|
| `database_management` | SQL-Ausführung, Schema-/Migration-Helpers, Tenant-DB-Routing |
| `embeddings_search` | Vektorsuche (pgvector) — semantisches Finden über Tenant-Inhalte |
| `minio` | Object-Storage CRUD (Files, Belege, Verträge) |
| `tasks` | Task/Reminder-CRUD mit Trigger-Hooks |
| `websearch` | externe Web-Suche |

## Konventionen
- Jedes Tool hat eigenes `README.md` und eigene MCP-Server-Definition.
- Geteilter Code (DB-Connect, Logging) kommt aus `/lib/`.
- Tools loggen alle Calls in die Logging-DB (Audit-Trail).
- Tools dürfen **nicht** andere Tools indirekt aufrufen — sie sind Blätter im Call-Graph.
