# Plan 06 — Debug-View V1

**Welle 2, Feature 6. Vision-Ref: §16.**

## Ziel

Eigene UI-Hauptachse für Tenant-Supporter und Plattform-Admins, in der man die Plattform live atmen sieht und vom fachlichen Symptom in zwei Klicks beim auslösenden LLM-Prompt landet. Information-dicht, kein Chat-Look — Devtools-Ästhetik.

## Schnittweise — V1 vs. V2

**V1 (dieser Plan) — drei Tabs:**
1. **Live** — Echtzeit-Strom aller Traces + Sub-Agent-Calls (SSE).
2. **Traces** — Trace-Achse, filter-/durchsuchbar, Drilldown auf Tools/LLM-Calls.
3. **MCPs & Agents** — alle MCPs + Sub-Agents aus Plan 05, Status, letzte Calls, Tool-Berechtigung.

**V2 (eigener späterer Plan) — drei weitere Tabs:**
4. **Entities** — freier Entity-Selector, Verlaufs-Tab pro Entität, fachliche Events.
5. **Change-Log** — globaler Strom aller `EntityChange`-Einträge.
6. **Errors** — `ErrorReport` + `error`-Events, Last-24h-Sicht.

Begründung Schnitt: V1 ist der Trace-zentrierte Drilldown, V2 ist die Entity-zentrierte Sicht. Beide brauchen unterschiedliche UI-Komponenten; getrennt bauen, getrennt testen.

## Schnittweise — was NICHT reinkommt

- **Keine Live-Editierung** — read-only.
- **Keine Mutation von Settings/Tenants** — das ist Admin View (§15).
- **Keine Query-Sprache** — Filter über UI-Form-Felder, keine Volltext-DSL.
- **Kein Export** (CSV, JSON-Bulk) in V1 — Trace-Daten kann man per `gh`-API / `psql` ziehen, wenn nötig.

## UI-Stack — Entscheidung

**Next.js unter `interface/app/debug/`.** Konsistent mit `interface/app/traces/page.tsx`, das bereits Next ist und das alte `gateway/ui_traces.py` (Inline-HTML) ablöst. Gateway liefert nur JSON-APIs (`/api/debug/...`), die UI lebt komplett in Next.

Konsolidierung im selben Plan:
- `gateway/ui_traces.py` wird entfernt.
- Der bestehende `/traces`-Route im Gateway gibt einen 308-Redirect auf `/debug/traces` (in der Next-App).
- Bestehender API-Endpoint `/api/traces` bleibt; Debug-Tab nutzt ihn weiter, ergänzt um Filter (siehe Tab 2).

## Routing & Auth

### Auth-Gate

Auth-Mechanik existiert bereits — `User.platform_role` (Werte heute: `"none"`, `"admin"`) und `TenantMembership.tenant_role` (heute: `"member"`, `"admin"`). Erweitert um:

- `platform_role = "supporter"` als zusätzlicher Wert. Plattform-Admin (`platform_role = "admin"`) ist immer auch Supporter.
- Auth-Helper `is_debug_user(user) -> bool`: `user.platform_role in {"admin", "supporter"}`.
- Tenant-Scope für Supporter: ein Supporter ist tenant-gebunden über seine `TenantMembership` (oder ein eigenes Feld `supporter_for_tenant`, falls Supporter über mehrere Tenants laufen sollen — V1: über bestehende Membership-Liste).
- Plattform-Admin sieht alle Tenants, Supporter nur die Tenants seiner Memberships.

Keine neue Migration nötig (existierende Spalten reichen), nur Seed-Updates für den Demo-User.

### URLs (Next.js)

- `/debug` → Next.js, redirect zu `/debug/live`
- `/debug/live` → Live-Tab (SSE-Stream-View)
- `/debug/traces` → Trace-Liste mit Filtern
- `/debug/traces/{trace_uid}` → Trace-Detail
- `/debug/mcps` → MCP-/Sub-Agent-Liste
- `/debug/mcps/{name}` → MCP-Detail mit letzten Calls

### API-Endpoints (Gateway)

- `GET /api/debug/stream` (SSE) — Live-Strom aller Events
- `GET /api/debug/traces` — Liste mit Filtern (erweitertes `/api/traces`)
- `GET /api/debug/traces/{uid}` — Detail (kann `/api/traces/{uid}` wiederverwenden)
- `GET /api/debug/mcps` — Liste aus `lib/agent.list_all_capabilities()`
- `GET /api/debug/mcps/{name}` — Detail
- `GET /api/debug/mcps/{name}/calls?limit=50` — Call-History

## Tab 1 — Live

### Layout

Drei vertikale Spalten:
- Links: Liste aktiver Traces (sortiert nach `started_at DESC`, Filter "läuft noch").
- Mitte: gewählter Trace, Live-Event-Strom (jeder neue Event-Row erscheint unten, scroll-pin am Ende).
- Rechts: aktive Sub-Agent-Calls (`sub_agent_started` ohne passendes `sub_agent_completed`).

### Mechanik

- SSE-Endpoint `/api/debug/stream` streamt **alle** Events.
  - Supporter: gefiltert auf `tenant_id ∈ memberships(user)`.
  - Plattform-Admin: ungefiltert, alle Tenants.
- Browser-seitig State-Maschine: pro `trace_uid` ein Event-Array, neu eingehende Events appenden, `trace_completed` → Trace bleibt noch **60s** in der "läuft noch / kürzlich fertig"-Liste sichtbar, dann fällt er raus.
- Sub-Trace-Darstellung im Live-Feed: **linear chronologisch**. Sub-Agent-Calls erscheinen als Inline-Karte mit `→ Sub-Trace öffnen` (Link auf die Detail-Seite des Sub-Trace). Kein Tree-View in V1.

### Code-Touchpoints

- `gateway/main.py`: neuer SSE-Endpoint `/api/debug/stream`, Tenant-Filter via Auth-Context.
- `lib/events.py` braucht einen globalen Multiplexer (heute ist `EventEmitter` per-trace) — ein leichter `EventBroker`, der jeden emittierten Event zusätzlich in eine globale Queue puscht (mit Tenant-ID als Filter-Key).
- `interface/app/debug/live/page.tsx` (neu): React-Komponente mit `EventSource` und 60s-Retention-Timer pro Trace.

## Tab 2 — Traces

### Liste

Tabelle mit Spalten:
- Started At, Tenant, Status (running/ok/error), User-Message-Snippet, Intent, Tool-Call-Count, Duration, Event-Count.

Filter über Form:
- Tenant (Dropdown bei Plattform-Admin, fix bei Supporter), Status, Zeitraum, Intent, min/max Duration.

Sortierung default `started_at DESC`. Pagination via `?limit=&offset=`.

### Detail

`/debug/traces/{trace_uid}`:
- Oben: Trace-Stammdaten (User-Message voll, Response voll, Dauer, Status).
- Mitte: chronologische Event-Liste, jedes Event als Karte:
  - `llm_request` / `llm_response` → Karten mit Prompt-Volltext (collapsible) + Response-Body.
  - `tool_call_started` / `tool_call_result` → zwei Karten, paaren über `call_id`. Argumente und Result als JSON-Treeview.
  - `sub_agent_started` / `sub_agent_completed` → klickbarer Sprung zum Sub-Trace (`sub_trace_uid`).
- Rechts: Mini-Map (Verlaufs-Übersicht für schnelles Springen bei langen Traces).

### Code-Touchpoints

- `lib/event_store.py`: `list_traces` existiert. Erweitern um Filter-Parameter (`intent`, `min_duration`, `max_duration`).
- `gateway/ui_traces.py`: **wird entfernt**. Code wandert nicht — die Next-Variante in `interface/app/traces/` ist schon vollständig.
- Gateway-Route `GET /traces`: 308-Redirect → `/debug/traces`.
- `interface/app/debug/traces/page.tsx` (neu): erweitert die existierende `traces/page.tsx` um Filter-Form und Plattform-Admin-Tenant-Dropdown.
- `interface/app/debug/traces/[uid]/page.tsx` (neu): Detail-Seite mit Mini-Map.

## Tab 3 — MCPs & Agents

### Liste

Zwei Sub-Sektionen, klar getrennt (nutzt Plan 05 `kind`):

**MCPs (passiv, `kind: tool`)**
- Spalten: Name, Endpunkt, Status (online/offline, durch Health-Ping), Tools-Count, letzte 5 Calls (Tool-Name + Dauer).

**Sub-Agent-Rollen (`kind: sub_agent`)**
- Spalten: Name, Beschreibung, aktive Calls (jetzt), letzte 5 Calls, ø-Dauer.

### Detail pro MCP/Agent

- Manifest-Output (`name`, `version`, `description`, `tools`).
- Letzte 50 Calls (aus `logging_db.event` filter auf `tool_call_started` mit `tool_name=...` oder `sub_agent_started` mit `role=...`).
- Tool-Berechtigung-Matrix pro Tenant (in V1 statisch: "alle Tenants haben Zugriff auf alle Tools" — Permission-System kommt später).

### Code-Touchpoints

- Nutzt `lib/agent.list_all_capabilities()` aus Plan 05 — bei Plan-05-Entscheidung "Sub-Agents als echte MCP-Server" sind das alles MCPs.
- Neuer Helper in `lib/event_store.py`: `tool_call_history(tool_name, limit=50)`, `sub_agent_history(role, limit=50)`.

## UI-Tech-Entscheidungen

- **Framework**: Next.js (siehe oben). Keine SSR-Templates im Gateway.
- **Tabellen**: keine externe Bibliothek in V1, native HTML + Module-CSS (wie `traces.module.css`). Filter via Form-State, kein Page-Reload.
- **Live-Stream**: native `EventSource` im Browser.
- **Monospace**: gesamte Debug-UI in Mono-Font (System-Default Mono), klar visuell vom User-Chat-UI getrennt.
- **Responsive / Mobile**: **Desktop-only in V1.** Fixed-width-OK. Debug-View ist Werkzeug für Supporter, nicht für Mobile-User.

## Pre-Checks — geklärt

1. **Läuft `/traces` SSR oder API?** → Beides existiert parallel. `gateway/ui_traces.py` ist Legacy-SSR, `interface/app/traces/page.tsx` ist die aktuelle Next-Variante, die `/api/traces` abruft. Debug-View wird **rein Next**, Legacy-SSR wird im Zuge dieses Plans entfernt.
2. **Auth-Mechanik für Supporter-Rolle** → Mechanik existiert (`User.platform_role`, heute `none|admin`). Erweitern um `supporter`. Keine Migration nötig.

## Tests

- Auth: nicht-Supporter bekommt 403.
- Trace-Liste mit verschiedenen Filtern.
- Trace-Detail mit Sub-Trace-Sprung.
- Live-Stream: neu eingehender Event taucht innerhalb von <1s im Browser auf.
- MCP-Status-Check robust gegen offline-MCP (kein Timeout, der die ganze Seite blockiert).

## Offene Fragen

- **UI-Stack**: Templates im Gateway oder Next-Komponente unter `interface/`? → entschieden: **Next.js** unter `interface/app/debug/`. Legacy-SSR (`gateway/ui_traces.py`) wird im Zuge des Plans entfernt.
- **Live-Stream-Scope**: pro Tenant oder global? → entschieden: **per-Tenant für Supporter, global für Plattform-Admin**. Auth-Filter im SSE-Endpoint anhand `platform_role` und Memberships.
- **Wie integrieren wir Sub-Trace-Bäume in der UI?** → entschieden: **linear chronologisch**, Sub-Traces als Inline-Karte mit "→ Sub-Trace öffnen"-Link. Tree-View ist V2-Material.
- **Retention im Live-Tab** — wie lange bleibt ein abgeschlossener Trace im Live-Tab sichtbar? → entschieden: **60s nach `trace_completed`**, dann fällt er raus. Wer ihn länger braucht, springt zum Trace-Tab.
- **Mobile/responsive?** → entschieden: **Desktop-only in V1**. Debug-View ist Supporter-Werkzeug, kein Mobile-Bedarf. Fixed-width OK.

## Aufwand

- Pre-Check + Auth: 1h
- Live-Tab inkl. Event-Broker: 4h
- Traces-Tab (Liste + Detail, basierend auf existierendem `/traces`): 3h
- MCPs-Tab: 3h
- Styling (Mono-Look, Tabellen-CSS): 1.5h
- Tests: 2h

**Gesamt V1: ~14h. Mit Abstand größtes Stück in Welle 1+2.**

Vorschlag: V1 in zwei Sub-Iterationen schneiden — erst Traces + MCPs (klassische Views), dann Live (SSE). Live ist optional eleganter, Traces+MCPs bringen sofort Wert.

## Abhängigkeiten

- **Plan 01** (trace_uid-Context) — weich, schon nützlich für Sub-Trace-Sprünge.
- **Plan 02** (Sub-Agent-Events) — hart, sonst sind die Lifecycle-Karten leer.
- **Plan 05** (MCP-Kind) — hart, sonst keine saubere MCP/Sub-Agent-Trennung.
- **Plan 04** (Change-Log) — weich, kommt erst in V2 zum Tragen.

## Umgesetzt am 2026-06-20

V1, zwei Sub-Iterationen — Sub-1 (Traces + MCPs) ist vollständig, Sub-2 (Live-SSE-Multiplexer) noch offen.

- Auth-Gate: `lib/auth.UserContext` erweitert um `platform_role`; neue Dataclass `DebugUser` + Dependency `require_debug_user` (401 ohne Cookie, 403 ohne `platform_role in {admin, supporter}`). Helper `is_debug_user_role()`.
- Seed: `scripts/seed_admin.py` setzt demo=admin, alice=supporter; `lib/seed.ensure_admin_user(platform_role=...)` Upgrade-only (none → supporter/admin, kein Downgrade).
- Legacy-SSR raus: `gateway/ui_traces.py` gelöscht; `/traces`-Route liefert 308-Redirect auf `/debug/traces`.
- Backend-API in `gateway/main.py`:
  - `GET /api/debug/me` — Self-Info inkl. memberships.
  - `GET /api/debug/traces` — Liste mit Filtern `tenant_id`/`status`/`intent`/`min_duration`/`max_duration`; Supporter wird auf seine Memberships post-gefiltert.
  - `GET /api/debug/traces/{uid}` — Detail, tenant-scope-gecheckt.
  - `GET /api/debug/mcps` und `GET /api/debug/mcps/{name}` — über `lib/agent.list_all_capabilities()` (Manifest-Discovery aus Plan 05).
  - `GET /api/debug/mcps/{name}/calls` — letzte `tool_call_started`/`sub_agent_started`-Events aus `logging_db.event`.
  - `GET /api/debug/stream` — SSE mit `ready`-Event + 15s-Heartbeat. Echter Event-Push folgt mit dem `EventBroker`-Multiplexer in Sub-Iteration 2.
- Next-Rewrites: alle `/api/debug/*` durchproxyt im `interface/next.config.ts`.
- Next-Pages unter `interface/app/debug/`:
  - `layout.tsx` — Auth-Probe via `/api/debug/me`, Tab-Nav (Live/Traces/MCPs).
  - `page.tsx` — Redirect auf `/debug/traces`.
  - `traces/page.tsx` (+ `traces/[uid]/page.tsx`) — Liste/Detail mit Filter-Form, Plattform-Admin sieht Tenant-Dropdown leer = "alle", Supporter sieht seine Memberships.
  - `mcps/page.tsx` (+ `mcps/[name]/page.tsx`) — Sektionen pro `kind` (`tool`/`sub_agent`/`mixed`/`unknown`), Detail-Page mit Manifest + Tool-Tabelle + letzten Calls.
  - `live/page.tsx` — `EventSource` auf `/api/debug/stream`, Status-Pill, Event-Liste (zeigt aktuell nur `ready`-Event + Hinweis, dass der Multiplexer noch fehlt).
  - `debug.module.css` — Monospace-Look (Devtools-Ästhetik), Desktop-only.
- API-Wrapper: `interface/lib/api/debug.ts` (`fetchDebugMe`, `fetchDebugTraces`, `fetchDebugTrace`, `fetchDebugMcps`, `fetchDebugMcp`, `fetchDebugMcpCalls`).
- Bewusst nicht umgesetzt (Sub-Iteration 2):
  - Globaler `EventBroker` in `lib/events.py` mit Tenant-Filter-Multiplexer — der Stream-Endpoint hat den Auth-Filter, das Pushen folgt.
  - Mini-Map für lange Traces im Detail-View.
  - Event-Typ-Filter im Detail-View (existiert in `/traces`, wandert mit der Konvergenz in V2).
