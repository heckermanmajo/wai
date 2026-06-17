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
