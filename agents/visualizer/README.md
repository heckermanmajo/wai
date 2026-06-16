# visualizer

**Typ:** Agent
**Status:** Skeleton

## Zweck
Erzeugt Visualisierungen: Charts, Diagramme, Dashboards. Bekommt Daten oder eine SQL-Frage und entscheidet welche Darstellung passt.

## Verantwortlichkeiten
- Chart-Typ wählen (Bar/Line/Pie/Heatmap/…) basierend auf Datenform
- Aggregations-Strategie vorschlagen
- Chart-Definition als JSON/Spec ausgeben (Renderer im `/interface`)
- Iteration auf User-Feedback ("eher als Linie", "stack die Balken")

## Genutzte Tools
- `tools/database_management` — Daten ziehen
- `tools/embeddings_search` — frühere Visualisierungen wiederverwenden

## DB-Zugriffe
- Tenant DB: read-only (Daten je nach Use-Case)

## MCP-Schnittstelle
TBD
