# Plan 02 — Sub-Agent-Lifecycle-Events

**Welle 1, Feature 2. Vision-Refs: §8 (Worker-Sichtbarkeit), Querschnitt Telemetrie.**

## Ziel

Drei neue Event-Typen im `EventEmitter`, die den Lebenszyklus eines Sub-Agent-Spawns sichtbar machen. Damit:
- Chat-UI kann live anzeigen, **welche Rolle gerade arbeitet** ("Sales-Support analysiert …").
- Debug-View (Plan 06) hat die Datenbasis für die Agent-Achse und das Live-Tab.
- Telemetrie-Auswertung kann pro Rolle Latenz, Erfolgsquote, Token-Verbrauch ziehen.

## Schnittweise — was NICHT reinkommt

- **Kein Result-Contract** als typisiertes Schema — kommt in Plan 10 (Welle 4). Wir geben aktuell nur `summary` als String rein, `outcome` bleibt leer.
- **Keine UI-Anzeige des Live-Status** — das ist eine Chat-UI-Iteration, kommt parallel oder direkt danach. Plan 02 produziert die Events, Renderung als separater Mini-Task.
- **Keine Quota-/Kostenrechnung** pro Sub-Agent — kommt mit MCP-Kind (Plan 05) und Settings.

## Datenmodell

**Keine neue Tabelle.** Die Events landen in `logging_db.event` (existiert), mit den neuen `event_type`-Werten:

- `sub_agent_started` — data: `{role, parent_trace_uid, sub_trace_uid, sub_chat_id, task_brief}`
- `sub_agent_progress` — data: `{role, sub_trace_uid, status_text}` (optional, vom Sub-Agent gepostet)
- `sub_agent_completed` — data: `{role, sub_trace_uid, summary, duration_ms, status, outcome_preview}`

`status` ∈ `{"ok", "error", "cancelled"}`. `outcome_preview` ist erstmal leer (Platzhalter für Plan 10).

## Code-Touchpoints

### `lib/events.py` — Vokabular erweitern

In `EVENT_TYPES` die drei neuen Strings hinzufügen. `sub_agent_progress` kann in `VOLATILE_EVENT_TYPES`, weil hochfrequent möglich (mehrere Statuszeilen pro Sekunde).

### `lib/event_store.py` — keine Änderung

`persist_event` ist event-typ-agnostisch. Die Events landen automatisch in `event`-Tabelle, sofern nicht volatile.

### `agents/manager/agent.py` — Emit beim Delegieren

Aktuelle Stelle: Zeile ~366, wo `name == "sales_support"` der Sub-Agent läuft. Vor `run_sales_support`:

```python
sub_trace_uid = new_trace_uid()
sub_chat_id = ...  # vom Chat-Create, siehe Plan 01
emitter.emit("sub_agent_started",
    role="sales_support",
    parent_trace_uid=emitter.trace_uid,
    sub_trace_uid=sub_trace_uid,
    sub_chat_id=sub_chat_id,
    task_brief=task[:200])
t0 = time.time()
try:
    result = await run_sales_support(task, tenant_slug=tenant_slug, sub_trace_uid=sub_trace_uid)
    status = "ok"
except Exception as e:
    result, status = str(e), "error"
emitter.emit("sub_agent_completed",
    role="sales_support",
    sub_trace_uid=sub_trace_uid,
    summary=result[:300],
    duration_ms=int((time.time() - t0) * 1000),
    status=status,
    outcome_preview="")
return result, status == "error"
```

### `agents/sales_support/agent.py` — eigener Trace + optionales `progress`

Der Sub-Agent öffnet seinen eigenen Trace (über `create_trace` mit der vom Parent übergebenen `sub_trace_uid`) und sein eigener `EventEmitter` läuft darauf. Optional kann er `sub_agent_progress` emittieren — bevorzugt aus dem Tool-Loop ("Tool X aufgerufen", "LLM-Round 3").

**Pragmatisch:** in dieser Iteration **kein** `progress` aus dem Sub-Agent erzwingen — das Event ist im Vokabular, Sub-Agents dürfen es nutzen, aber pflicht ist nur `started`/`completed` vom Manager.

### Helper für künftige Sub-Agents

Eine Mini-Funktion `emit_sub_agent_call(emitter, role, sub_chat_id, fn, *args, **kwargs)` in `lib/agent.py`, die das Pattern kapselt. Damit braucht der nächste Sub-Agent (Archivar, Researcher) nur den Helper, nicht die ganze Boilerplate.

## SSE-Integration

`/chat/stream`-SSE-Endpoint streamt alle Events ohnehin schon. Die neuen Event-Typen kommen automatisch am Client an. Frontend muss sie nur erkennen.

## UI-Punkte (Vorschau, nicht in dieser Iteration)

Chat-UI bekommt eine Status-Zeile zwischen User- und AI-Message:
- `sub_agent_started` → "🔧 Sales-Support arbeitet …"
- `sub_agent_progress` → ersetzt Status-Text live
- `sub_agent_completed` → Status-Zeile wird "✓ Sales-Support hat geantwortet (1.2s)"

Klick auf die Zeile öffnet den Sub-Chat (sobald Plan 01 den Anker liefert + Sub-Chat-UI-Tab existiert).

## Tests

- Manager-Agent emittiert exakt 1× `sub_agent_started` und 1× `sub_agent_completed` pro Delegation.
- `sub_trace_uid` ist überall konsistent.
- Bei Sub-Agent-Exception: `status="error"`, `summary` enthält Fehler-Text.
- SSE-Stream liefert die neuen Events sauber.

## Offene Fragen

- **`task_brief`-Länge** — voller Prompt oder gekürzt? Tendenz: gekürzt (200 Zeichen), voller Brief steht im Sub-Trace selbst.
  → **entschieden (2026-06-20):** gekürzt auf 200 Zeichen. Der volle Brief landet ohnehin als erste User-Message im Sub-Chat (siehe Persist-Pfad unten).
- **`progress` vom Sub-Agent — Pflicht oder Best-Effort?** Tendenz: Best-Effort. Sonst wird jeder Sub-Agent zur Pflicht-Erweiterung.
  → **entschieden (2026-06-20):** Best-Effort. Vokabular ist da; aktuell emittiert kein Sub-Agent `sub_agent_progress`. Nachziehbar pro Sub-Agent ohne Plan-Änderung.
- **Nested Sub-Agents (Sub-Agent ruft Sub-Sub-Agent)** — der `parent_trace_uid` ist dann nicht mehr Top-Level. Brauchen wir `top_trace_uid` zusätzlich für Drilldown? Wahrscheinlich nicht in V1, der Trace-Baum lässt sich rekursiv über `parent_trace_uid` aufbauen.
  → **entschieden (2026-06-20):** Nein, kein `top_trace_uid`. Rekursive Auflösung via `parent_trace_uid`. Falls Drilldown in Welle 3+ teuer wird, nachziehen.
- **Cancellation** — wie cancelt der User einen laufenden Sub-Agent? Nicht in dieser Iteration, aber das Event `sub_agent_completed` mit `status="cancelled"` ist vorbereitet.
  → **entschieden (2026-06-20):** Nicht in dieser Iteration. `status="cancelled"` bleibt im Vokabular reserviert.

### Neue offene Fragen aus der Durchsprache (2026-06-20)

- **Eigener Sub-Emitter mit Fan-Out vs. Parent-Emitter teilen?** Sub-Emitter braucht einen eigenen `sub_trace_uid` für sauberen DB-Trace, aber Events müssen im SSE-Stream des Parents auftauchen.
  → **entschieden:** Eigener `SubEventEmitter` mit `parent_emitter`-Referenz. Bei `emit()` wird das Event zusätzlich per `forward()` in die Parent-Queue gepusht — der SSE-Pump im Gateway sieht so beide Trace-Ebenen. Persistenz läuft pro Event mit dem `trace_uid` des Events selbst, d.h. Sub-Events landen automatisch unter `sub_trace_uid` in `logging_db.event`. Sub-Trace bekommt eigene `create_trace`/`finalize_trace`-Klammer im Helper.
- **Wann wird der Sub-AiChat angelegt?**
  → **entschieden:** Vom Helper `emit_sub_agent_call` in `lib/agent.py` — direkt vor `sub_agent_started`. Felder: `parent_chat_id`, `parent_tool_call_id`, `depth+1`, `target_cls`/`target_id` werden vom Parent-Chat geerbt (Plan-01-Anker). `agent_name = role`. Title default "Sub-Chat (<role>)".
- **Persistiert der Sub-Agent seine Messages?**
  → **entschieden:** Ja, voller Persist-Pfad analog Manager (User-Brief als `user`-Message + Assistant-Replies + Tool-Calls + ChatArtifact). Heißt: `_persist_exchange` wird aus `agents/manager/agent.py` in einen generischen Helper `lib/chat_persist.py` extrahiert, Manager **und** Sales-Support nutzen ihn.
- **Error-Handling im Helper?**
  → **entschieden:** Exception im Helper fangen → `sub_agent_completed` mit `status="error"`, `summary=str(e)[:300]`. Tool-Result an den Manager-LLM ist der Fehlertext. Heutiges Verhalten (Exception bubbelt bis `_dispatch_tool_call`-Fängerklausel) ändert sich damit minimal: Es bleibt ein "Tool-Fehler"-String im Tool-Channel, aber jetzt mit sauberem Telemetrie-Trail.

## Scope-Anpassung (2026-06-20, Durchsprache vor Umsetzung)

Aus den oben getroffenen Entscheidungen folgt eine Scope-Erweiterung gegenüber dem ursprünglichen Plan:

- **`lib/chat_persist.py` (neu)** — Extraktion von `_persist_exchange`, `_extract_artifact`, `_load_history`, `CRM_TOOL_ARTIFACT_MAP` aus dem Manager. Manager refactored, Sub-Agent nutzt es ebenfalls.
- **`SubEventEmitter` in `lib/events.py`** — Subklasse mit Parent-Forwarding. `EventEmitter` bekommt eine `forward(ev)`-Methode, die fertige Events ohne Re-Stamp in die eigene Queue legt.
- **Sub-Trace-Klammer im Helper** — `create_trace(sub_trace_uid, ...)` vor Spawn, `finalize_trace(sub_trace_uid, ...)` in finally.

Damit landet Plan 02 eher bei ~4h Arbeit, nicht 1.5h. Bewusst aufgenommen, weil der Sub-Persist-Pfad in jeder Folgewelle (Debug-View, Archivar, weitere Sub-Agents) sonst doppelt gebaut werden müsste.

## Aufwand

- Vokabular erweitern: 5 min
- Manager-Agent-Integration: 45 min
- Helper-Funktion: 20 min
- Tests: 30 min

**Gesamt: ~1.5h. Erweitert sich, wenn wir gleich die Chat-UI-Anzeige bauen.**

## Abhängigkeiten

- Plan 01 (`sub_chat_id` aus dem persistent angelegten Sub-Chat).
- Sonst keine.

## Umgesetzt am 2026-06-20

- `lib/events.py` — drei neue Event-Types in `EVENT_TYPES` (`sub_agent_started`, `sub_agent_progress`, `sub_agent_completed`). `sub_agent_progress` zusätzlich in `VOLATILE_EVENT_TYPES`. Neue `EventEmitter.forward(ev)`-Methode legt fremde Events ohne Re-Stamp in die Queue. Neue Klasse `SubEventEmitter(EventEmitter)` mit `parent_emitter`-Referenz: jedes `emit()` wird zusätzlich per `parent_emitter.forward()` ge-fanned-out, damit der Parent-SSE-Stream Sub-Events live sieht (mit ihrem eigenen `sub_trace_uid`).
- `lib/chat_persist.py` — **neu**. Extraktion von `_persist_exchange`, `_extract_artifact`, `_load_history`, `CRM_TOOL_ARTIFACT_MAP` aus `agents/manager/agent.py`. Manager nutzt jetzt die externen Helfer; Sales-Support nutzt sie ebenfalls für seinen Sub-Chat-Persist. Keine Verhaltensänderung im Manager-Pfad.
- `lib/agent.py` — neuer Helper `emit_sub_agent_call(*, parent_emitter, role, parent_chat_id, parent_tool_call_id, tenant_slug, user_id, task, fn, **fn_kwargs)`. Klammert: Anker-Lookup vom Parent-Chat, Sub-AiChat-Insert (mit `parent_chat_id`, `depth+1`, geerbtem Anker), `new_trace_uid()` + `create_trace()` in `logging_db`, `SubEventEmitter`-Aufbau, `sub_agent_started` auf Parent, `set_actor("ai", role)` + `set_trace_uid(sub_trace_uid)` mit Restore via `prev_actor`/`prev_trace`, Aufruf der `fn`, Exception-Fang (`status="error"`, `summary=str(e)[:300]`), `sub_agent_completed` auf Parent, `finalize_trace`. `task_brief` und `summary` werden auf 200/300 Zeichen gekürzt. `parent_tool_call_id=0` bleibt offen — die DB-Row für `AiToolCall` existiert erst nach `_persist_exchange` des Parents (Folgearbeit: optional in einer eigenen Iteration nachreichen).
- `agents/manager/agent.py` — Import von `emit_sub_agent_call` + `get_user`. Lokale `_load_history`/`_persist_exchange`/`_extract_artifact`/`CRM_TOOL_ARTIFACT_MAP` raus (jetzt aus `lib.chat_persist`). `_dispatch_tool_call(...)` bekommt neue Pflicht-kwargs `parent_emitter`, `parent_chat_id`; der `sales_support`-Branch ruft den Helper statt direkt `run_sales_support`. `_run_tool_round`/`_run_tool_loop`/`_handle_lead_chat` reichen `chat_id` durch (`*, chat_id: int`). `chat()` ruft `_handle_lead_chat(..., chat_id=chat_id)`. Sicherheitsfallback wenn `emitter is None` beim Sub-Spawn: liefert Tool-Fehler-String statt zu crashen.
- `agents/sales_support/agent.py` — komplett umgebaut. Neue Signatur: `run_sales_support(task, *, sub_emitter, sub_trace_uid, sub_chat_id, tenant_slug, user_id)`. Eigener Tool-Loop (`_run_tool_round`/`_run_tool_loop`) emittiert dieselben Events wie der Manager (`mcp_connected`, `llm_request`, `llm_response`, `tool_call_started`, `tool_call_result`). Am Ende: `trace_completed` + `persist_exchange(sub_chat_id, tenant_slug, task, new_messages)` schreibt User-Brief + Assistant + Tool-Calls in die Sub-Chat-Row. `SalesSupportAgent`-OO-Wrapper entfernt (war toter Code; keine Importer).
- **Tests** (Smoke, im `wai-gateway`-Container ausgeführt):
  - Vokabular vollständig + `sub_agent_progress` korrekt volatile.
  - `EventEmitter.forward()` legt fremdes Event ohne Re-Stamp ab; Sequence-Counter unverändert.
  - `SubEventEmitter` pumpt Events 1:1 in Parent-Queue, `sub_trace_uid` erhalten.
  - `emit_sub_agent_call` Pfad A (Success): genau 1× `sub_agent_started` + 1× `sub_agent_completed` auf Parent, `status="ok"`, `sub_trace_uid` konsistent zwischen beiden Events.
  - Sub-AiChat in tenant-DB: `parent_chat_id`, `depth=1`, `agent_name="sales_support"`.
  - Pfad B (Exception): Helper fängt `RuntimeError("boom")`, liefert `is_error=True` + `summary` mit Fehlertext, `sub_agent_completed.status="error"`.
  - Anker-Vererbung: Parent mit `target_cls="ai.chat"`, `target_id=42` → Sub-Chat erbt beide Felder.
  - `logging_db.trace` für `sub_trace_uid` mit `status="ok"` und Event-Count > 0 geschrieben (= `create_trace` + `finalize_trace` korrekt geklammert).
- **Bewusst raus** dieser Iteration:
  - **`sub_agent_progress`**-Emission im Sales-Support (Best-Effort-Entscheidung): Vokabular ist da, Sub-Agent emittiert nichts; nachziehbar ohne Plan-Änderung.
  - **`parent_tool_call_id`-Backfill**: bleibt `0`, weil `AiToolCall`-Row erst nach `_persist_exchange` des Parents existiert. Sauberer Link entweder via ContextVar-Pass-Through oder Post-Persist-Update — out of scope.
  - **Streaming-Deltas im Sales-Support**: Sub-Agent ruft `chat.completions.create` non-streaming (wie heute); nur `llm_request`/`llm_response`-Events, keine `llm_delta`. Streaming-Refactor optional.
  - **Sub-Chat-UI** (Tabs, Klick auf Status-Zeile): kommt mit Chat-UI-Iteration / Plan 06.
- Commit: siehe `git log --grep "Plan 02"`.

### Vision-Status

- **§8 (Worker-Sichtbarkeit):** `fehlt` → **teilweise**. Sub-Agent-Spawn ist nun in Live-Telemetrie + persistentem Sub-Chat sichtbar; UI-Live-Anzeige der Worker-Statuszeile fehlt (separater Mini-Task).
- **§10 (Nested Chats / Sub-Chats):** `teilweise` (nach Plan 01) → **teilweise**, jetzt aber mit voller Sub-Chat-Schale + Sub-Persist. Result-Contract (Plan 10) und UI fehlen weiter.
- **§18 (Explorer):** unverändert `fehlt komplett`.
