# manager

**Typ:** Agent (Orchestrator)
**Status:** **erste lauffähige Demo** — siehe Root-README → Quickstart.

## Zweck
Top-Level-Einstiegspunkt für User-Requests. In der Demo-Version aktuell ein einfacher Chat-Agent mit Function-Calling; später routet er an Fach-Agents weiter und koordiniert Multi-Agent-Workflows.

## Aktueller Stand (Demo)
- **Provider:** OpenAI `gpt-5.5` — hardgecodet in [`provider.py`](provider.py). API-Key via `OPENAI_API_KEY`.
- **Entry-Point:** `agent.chat(history: list[dict], user_message: str) -> dict`
- **Tool-Use:** kann max. 1× pro Turn `get_time` am Mock-MCP-Server (`MCP_MOCK_URL`) aufrufen — single-round Function-Calling.
- **System-Prompt** in `agent.py` → `SYSTEM_PROMPT`.
- **Logging:** über `lib.logging` (Logger `wai.agents.manager.*`).

## Datei-Struktur
| Datei | Inhalt |
|---|---|
| `agent.py`    | Chat-Funktion, Tool-Loop, System-Prompt |
| `provider.py` | hartkodierter OpenAI-Client (`gpt-5.5`) |
| `README.md`   | diese Datei |

## Nächste Schritte (geplant)
- Mehrere Tool-Calls pro Turn (Multi-Round-Loop)
- Routing-Logik zu Fach-Agents (`coach`, `finance`, …)
- Persistierung von `Chat` + `Message` in der Tenant-DB
- Streaming-Antworten an das Frontend
- Provider abstrahieren (`lib/providers/`), damit Modell-Wechsel möglich ist
