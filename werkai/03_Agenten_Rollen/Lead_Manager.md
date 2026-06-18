# 🤖 Lead-Manager / Sales Support (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der Lead-Manager / Sales Support qualifiziert eingehende Kundenanfragen (Leads) und bereitet diese für den Vertrieb oder die Angebotskalkulation vor. Er filtert unproduktive Anfragen frühzeitig heraus.

**Tracer Bullet Status:** ✅ Implementiert — Erster durchgängiger Datenfluss via MCP-Protokoll (FastMCP SSE). Siehe [`TASK_MEMORY/2026-06-18-2026-06-18-tracer-bullet-lead-manager.md`](../../TASK_MEMORY/2026-06-18-2026-06-18-tracer-bullet-lead-manager.md).

## 2. Aufgaben & Fähigkeiten
- **Lead-Qualifizierung**: Abfragen von Projekt-Details (z.B. Budget, Zeitrahmen, Gewerk) via E-Mail oder WhatsApp.
- **Ausschreibungs-Analyse**: Auslesen wichtiger Anforderungen aus öffentlichen oder privaten Bauausschreibungen.
- **Kunden-Historie**: Zusammenfassung vergangener Interaktionen mit dem Kunden, um dem Geschäftsführer vor dem Telefonat Kontext zu liefern.
- **MCP-Tool-Integration**: Der Agent lädt dynamisch MCP-Tools per SSE-Client und führt Multi-Round-Tool-Loops aus (MAX_TOOL_ROUNDS=5). Implementiert in [`agents/manager/agent.py`](../../agents/manager/agent.py).

## 3. Tooling & Integrationen
- **CRM-Verbindung**: Schnittstelle zur PostgreSQL/Baserow Kundendatenbank.
- **Parser**: Dokumenten-Parser zur Analyse von Leistungsverzeichnissen (PDFs/Word-Dateien).
- **Kommunikation**: WhatsApp- und E-Mail-Templates zur automatisierten Einholung fehlender Kunden-Informationen.
- **MCP Mock Server**: [`mcp_servers/mock_mcp/server.py`](../../mcp_servers/mock_mcp/server.py) — FastMCP SSE auf Port 8001 mit 3 Tools: `hole_kunden_status`, `erstelle_kunden_notiz`, `suche_kunden`. In-Memory KUNDEN_DB mit 3 Testkunden (meier, schmidt, mueller).
- **LLM-Provider**: [`agents/manager/provider.py`](../../agents/manager/provider.py) — Zwei-Tier AsyncOpenAI (Tier1=gpt-4o-mini für Intent-Klassifikation, Tier2=gpt-4o für Reasoning/Tool-Calling).
- **Gateway**: [`gateway/main.py`](../../gateway/main.py) — FastAPI-Endpunkt mit `tenant_id`-Propagation.
