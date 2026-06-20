# Plan 08 — Fachliche Events am Vorgang V1

**Welle 3, Feature 2. Vision-Ref: §2 (Events auf Vorgängen), berührt §1 (Process aus Plan 07), §11 (Visualisierung — bewusst NICHT in V1), §16 (Debug-View, Konsumenten-Seite), §26 (Change-Log).**

## Ziel

Fachliche Events als eigene Tenant-Entität — die **kuratierte Bedeutungs-Timeline** ("Statuswechsel", "Anruf am 12.6.", "Mail rausgegangen", "Termin"), klar getrennt vom universellen Change-Log (Feld-Diffs) und von der Telemetrie-Tabelle `logging_db.event` (technisch pro Chat-Runde). Polymorpher Anker auf beliebige Entities, primär an Process. **Auto-Erzeugung aus dem Change-Log** für eine schmale, kuratierte Whitelist (z.B. `core.process.status`) als Hebelmechanik — pro Tenant/Workflow später erweiterbar.

Damit ist die Grundlage für (a) die Vorgangs-Timeline-UI (eigener Plan), (b) die `trace_uid`-Brücke vom Vorgang in den Debug-View, und (c) die spätere Workflow-Engine (Events sind die natürlichen Trigger).

## Schnittweise — V1 vs. spätere Iterationen

**V1 (dieser Plan):**
- Neue Tenant-Entität für fachliche Events (Tabelle `event` in `tenant_db`, Class-Name siehe Offene Frage 1).
- Polymorpher Anker (`target_cls` + `target_id`) → primär an `core.process`, aber strukturell offen für jedes registrierte Entity.
- Optionales `trace_uid` (leer = rein menschliches Event) — Brücke zu `logging_db.trace`.
- `actor_type` (`human` / `ai` / `system`) + `actor_id` + `agent_name` — gefüllt aus `tenant_context` analog zum Change-Log (Plan 04).
- Semantic-Sync integriert (Events sind durchsuchbar, Vision §2).
- Change-Log → Event-Auto-Erzeugung als **Listener mit Whitelist** im selben after-commit-Pfad wie der Change-Log. V1-Whitelist: nur `("core.process", "status")` → Event-Typ `status_changed`.
- Schlanker MCP-Tool-Bundle (siehe Offene Frage 3 für den MCP-Cut): manuelles `event_log`, `event_list`, `event_get`, `event_delete` (soft).
- Auto-Integration mit Welle-1/2-Infrastruktur (Change-Log, Semantic-Sync, Settings, Debug-View).

**Spätere Iterationen (eigene Pläne):**
- **Vorgangs-Timeline-UI** (gemeinsam mit Explorer §18 oder als eigene Detail-Sicht) — zeigt Events chronologisch, mit Drill-Down-Pfeil in den Debug-View über `trace_uid`.
- **Erweiterbare Auto-Regeln** (§7-vorbereitend): UI/Konfig, mit der man pro Tenant zusätzliche Feld→Event-Mappings setzt; in V1 ist die Whitelist hartkodiert + per Setting überschreibbar.
- **Event-Reaktionen** (Workflow-Trigger, §7) — Events als Eingangsfilter für Workflows.
- **Event-Visualisierungen** (§11): Burndown, Aktivitäts-Heatmap.
- **Externe Events** (§20): Mail-Ingest, Kalender-Sync → erzeugen automatisch Events.

## Schnittweise — was NICHT in V1 reinkommt

- **Keine Timeline-UI** in V1 — Detail-Sicht hängt am EntityOverlay (Plan 07), neuer Tab "Verlauf" kann erstmal Change-Log + Events parallel anzeigen, ist aber **nicht** Pflicht für V1-Abnahme. Vision-Konformes Rendering kommt mit Explorer/Visualisierung.
- **Keine Listen-/Filter-Page** über alle Events eines Tenants.
- **Keine Workflow-/Reaktions-Bindung** — Events sind in V1 Read-Only-Konsumenten-Daten plus reine Auto-Erzeugung, keine Trigger.
- **Keine Event-Typ-Registry** mit Schema-Validierung — `event_type` ist Freitext-String, V1-Defaults dokumentiert, kein Validator.
- **Keine Edit-Funktion** — manuelle Events sind nach Erstellen unveränderlich (Audit-Charakter). Korrektur = neues Event + Soft-Delete des alten.
- **Keine Mail-/Kalender-Ingest-Quellen** — kommt mit dem Externe-Integrationen-Plan (§20).
- **Kein automatisches Event aus jedem Change-Log-Eintrag** — explizit kuratierte Whitelist. Default-Whitelist ist klein; Anwendern bleibt freigestellt, sie zu erweitern.
- **Keine Migration/Backfill** historischer Change-Log-Einträge — Auto-Erzeugung greift erst ab Plan-08-Deployment.

## Datenmodell

### Tabelle `event` (Tenant-DB)

```text
id                int PK            -- aus IdMixin
created_at        datetime          -- aus TimestampMixin
updated_at        datetime          -- aus TimestampMixin
is_deleted        bool default F    -- aus SoftDeleteMixin

happened_at       datetime NOT NULL -- Zeitpunkt des Geschehens (≠ created_at)
                                    --   bei Auto-Events == created_at,
                                    --   bei manuellen kann der User es rückdatieren
event_type        str(64) NOT NULL  -- "status_changed" | "call_logged" | "mail_sent" |
                                    -- "meeting_scheduled" | "manual_entry" | <freitext>
title             str(255) default ""-- kurze Headline für die Timeline
                                    -- z.B. "Status: in_arbeit → wartet_auf_kunde"
body              text default ""   -- Freitext-Detail (Markdown), semantisch indexiert

target_cls        str(64) NOT NULL  -- polymorpher Anker (primär "core.process"),
target_id         int NOT NULL      --   Konvention: beide leer/0 wäre erlaubt,
                                    --   wir erlauben das aber NICHT — Event braucht Anker.
                                    --   (Offene Frage 4)

actor_type        str(16) default "system"  -- "human" | "ai" | "system" (auto-trigger)
actor_id          int default 0     -- user_id bei human, agent-ref bei ai, 0 bei system
agent_name        str(64) default ""-- "manager" | "sales_support" | ...

trace_uid         str(36) default ""-- optional, Brücke zu logging_db.trace
                                    --   leer bei reinen Mensch-Events ohne Chat-Kontext
source            str(32) default "manual"  -- "manual" | "auto_change_log" | "auto_workflow"
                                    --   später: "mail_ingest" | "calendar" (§20)
source_ref        str(255) default ""  -- optional, freier Identifier auf die Quelle
                                    --   z.B. bei auto_change_log: "entity_change:<id>"

data              jsonb default '{}'-- typ-spezifisches Detail-Bag.
                                    --   Bei status_changed: {"old": "...", "new": "..."}
                                    --   Bei call_logged:   {"duration_s": 600, "phone": "..."}
                                    --   Wir validieren das in V1 NICHT — kuratiert lassen.
```

**Indices:**
- `(is_deleted, target_cls, target_id, happened_at DESC)` — Timeline-Query "letzte Events zu Vorgang X".
- `(trace_uid)` — Drill-Down Debug-View → fachliches Event.
- `(event_type, happened_at)` — Filter-/Statistik-Queries.
- `(source, source_ref)` — Idempotenz-Check für Auto-Events ("habe ich diesen change_log-Eintrag schon umgesetzt?").

**Bewusst keine FK-Constraints** (Repo-Konvention).

### Semantic-Sync

Wie Process: `BusinessEvent` implementiert `get_resource_type/_name/_short/_markdown/_url` und wird in `lib/semantic_sync.register_sync_listeners` pairs eingetragen. Search-Index findet ein Event über Titel + Body. `__change_log__ = False` (Offene Frage 8): Events sind selbst Audit-artig, taucht NICHT im Change-Log auf.

### Migration

Pfad: `alembic/tenant/versions/YYYYMMDD_0011_event.py`.

- `revision = "tenant_0011"`, `down_revision = "tenant_0010"`.
- `op.create_table("event", …)` mit obigen Spalten + vier Indices.
- Downgrade: `op.drop_table("event")`.

## Code-Touchpoints

### Neu

- `lib/entities/tenant/event.py` — Class-Name siehe Offene Frage 1. `@register_entity("core.event")` (Alias-Vorschlag, könnte je nach Class-Name auch "core.business_event" sein). Resource-Adapter wie bei Process.
- `alembic/tenant/versions/YYYYMMDD_0011_event.py` — siehe Datenmodell.
- `lib/business_events.py` — Helper-Modul mit:
  - `log_event(target_cls, target_id, event_type, *, title, body, happened_at=None, data=None, source="manual", source_ref="") -> int` — schreibt ein Event in der aktuellen Tenant-Session (oder mit `session_for_tenant(slug)` als Convenience). Füllt `actor_type/actor_id/agent_name/trace_uid` automatisch aus `lib.tenant_context`.
  - `iter_auto_rules(target_cls: str) -> Iterable[AutoRule]` — liefert die V1-Whitelist (hardcoded + per Settings überschreibbar).
- `lib/audit_to_event.py` — der Auto-Erzeugungs-Listener. Hängt sich an dasselbe `after_commit` wie der Change-Log, aber NACH dem Change-Log-Drain (Reihenfolge wichtig), liest die soeben geschriebenen `EntityChange`-Einträge per `source_ref` und materialisiert daraus Events. Idempotent: prüft pro `EntityChange.id` per `source_ref="entity_change:<id>"`, ob schon ein Event existiert.
- `mcp_servers/process_mcp/server.py` ODER neuer `events_mcp` — siehe Offene Frage 3. Tools: `event_log`, `event_list`, `event_get`, `event_delete`.
- Smoke: `scripts/smoke_events.py` analog zu `smoke_process.py`.

### Berührt

- `lib/entities/tenant/__init__.py` — Re-Export.
- `lib/semantic_sync.py` — `Event` zu pairs hinzufügen.
- `lib/audit.py` — vermutlich keine Änderung; der Hook liefert die `EntityChange`-Liste, der Auto-Event-Listener registriert sich daneben am `after_commit`. **Sicherzustellen**: Reihenfolge der `after_commit`-Listener — der Auto-Event-Listener muss NACH dem Change-Log-Drain laufen, damit er die geschriebenen Einträge findet. Alternative: Auto-Event-Listener konsumiert NICHT die persistierten Einträge, sondern direkt die Outbox vor dem Drain. Beides sauber lösbar — Detail beim Implementieren.
- `lib/settings.PLATFORM_DEFAULTS` — neuer Key `events.auto_rules.<target_cls>` mit Default-Whitelist. Beispiel:
  ```python
  "events.auto_rules.core.process": [
      {"field": "status", "event_type": "status_changed",
       "title_template": "Status: {old} → {new}"},
  ],
  ```
- Falls eigener `events_mcp`: `docker-compose.yml` (Service auf Port 8506), `lib/agent.MCP_ENDPOINTS` (Eintrag `("events", …)`), `start_local.sh` (kein zusätzlicher Seed nötig — Events entstehen automatisch beim ersten Status-Wechsel).

### Auto-Integration (kein eigener Code nötig)

- **Change-Log:** `BusinessEvent` hat `__change_log__ = False` (Offene Frage 8) — Events tauchen NICHT im Change-Log auf. Audit-über-Audit-Rauschen vermieden. Manuelle Korrekturen über soft-delete + neues Event.
- **Semantic-Sync:** Wenn `Event` in pairs eingetragen ist, läuft die Fassade automatisch (analog Process).
- **Debug-View (Plan 06):** Sobald die Event-Tabelle existiert, kann der Debug-View Events zu einem `trace_uid` listen — keine neue Logik dort nötig, nur ein Tab/Filter, wenn gewünscht (V1 nicht Pflicht).

## MCP-Anbindung

Siehe Offene Frage 3 zum Cut. Tool-Manifest (egal in welchem MCP):

- `event_log(target_cls, target_id, event_type, title?, body?, happened_at?, data?) -> {id}` — manuelles Event eintragen.
- `event_list(filter?: {target_cls?, target_id?, event_type?, since?, until?, trace_uid?}, limit?, offset?) -> [{…}]`
- `event_get(id) -> {…}`
- `event_delete(id) -> {ok}` — soft.

**Bewusst nicht im V1-MCP:** Edit-/Update-Tool, Auto-Rule-Konfig-Tool, Batch-Import-Tool.

## UI-Punkte

**V1 minimal:**
- `interface/components/overlays/EntityOverlay.tsx` (Tab "Verlauf"): kann optional Events zusätzlich zum Change-Log einblenden. Nicht Pflicht für V1-Abnahme — die Hauptarbeit ist Datenmodell + Auto-Erzeugung; die UI-Hochzeit kommt mit dem Timeline-Plan.
- Im Debug-View (Plan 06): kein Pflicht-Hook in V1, aber sobald der Tab steht, ist die `trace_uid → event[]`-Liste ein 5-Zeilen-Query.

**Bewusst später:**
- Eigene Vorgangs-Timeline-Komponente.
- Globale Event-Listen-Page.
- Event-Erstellungs-Dialog im UI (in V1 macht der Agent es per MCP-Tool).

## Tests

**Smoke-Cases (in `scripts/smoke_events.py`):**

1. **Schema/Migration:** `tenant_0011` upgrade/downgrade greift sauber, Defaults stimmen.
2. **Manuelles Event:** `log_event(target_cls="core.process", target_id=<pid>, event_type="call_logged", title="Anruf von Kunde", body="...")` legt einen Event mit `actor_type` aus `tenant_context` an. `event_get` liefert ihn zurück.
3. **`trace_uid`-Brücke:** Wenn beim `log_event` ein `trace_uid` im `tenant_context` gesetzt ist, landet es im Event. Sonst leer.
4. **Auto-Erzeugung aus Status-Wechsel:** `set_status(<pid>, "in_arbeit")` aus dem `process_mcp` triggert nach Commit (a) einen `EntityChange`-Eintrag (Plan 04) und (b) genau einen Event mit `event_type="status_changed"`, `source="auto_change_log"`, `source_ref="entity_change:<id>"`, `data={"old":"neu","new":"in_arbeit"}`. **Idempotenz:** ein zweiter, identischer Status-Setz-Versuch erzeugt KEINEN doppelten Event (gleicher `source_ref`).
5. **Selektive Whitelist:** Update auf `description` erzeugt einen Change-Log-Eintrag, aber KEINEN Event (description nicht in der Default-Whitelist).
6. **Polymorpher Anker:** `event_list(filter={target_cls: "core.process", target_id: <pid>})` liefert chronologisch sortiert.
7. **Soft-Delete:** `event_delete(id)` setzt `is_deleted=True`, taucht in `event_list` nicht mehr auf, schreibt **keinen** Change-Log-Eintrag (`__change_log__ = False` per Offene-Frage 8).
8. **Semantic-Sync:** Nach `log_event`-Commit existiert eine `SemanticFassade` für das Event; nach Body-Update (falls wir Edit unterstützen, in V1 nein) ändert sich `content_hash` — entfällt in V1.
9. **MCP-Tool-Smoke:** Happy-Path über `event_log` → `event_get` → `event_list` → `event_delete`.

## Offene Fragen

1. **Name-Konflikt:** Es gibt schon `lib/entities/logging/event.Event`. Eine zweite `Event`-Klasse in `lib/entities/tenant/event.py` würde im selben Namespace im Re-Export aus `lib.entities.tenant` mit `lib.entities.logging.Event` kollidieren, sobald irgendwo beide Pakete im selben Modul importiert werden. **Optionen:**
   - **a)** Tenant-Klasse heißt `BusinessEvent` (Tabelle wahlweise `event` oder `business_event`).
   - **b)** Tenant-Klasse heißt `DomainEvent`.
   - **c)** Tenant-Klasse heißt einfach `Event`, Importe disziplinieren wir explizit (`from lib.entities.tenant import Event` vs. `from lib.entities.logging import Event as TraceEvent`).
   V1-Empfehlung: **a) `BusinessEvent`** mit Tabelle `event` (VISION sagt explizit `tenant_db.event`). Class-Name englisch konsistent, Tabellen-Name folgt VISION. Alias `core.event`. → **entschieden: a) `BusinessEvent`, Tabelle `event`, Alias `core.event`** (2026-06-20).

2. **Auto-Trigger-Mechanismus — wo lebt die Whitelist?**
   - **a)** Hardcoded Dict in `lib/business_events.py` (V1-pragmatisch, später per Setting überschreibbar).
   - **b)** Direkt im Setting-Resolver: `events.auto_rules.<target_cls>` als Liste, Plattform-Default in `PLATFORM_DEFAULTS`.
   - **c)** Eigene Tabelle `auto_event_rule` im Tenant.
   V1-Empfehlung: **b)** — Plattform-Default in `PLATFORM_DEFAULTS`, pro Tenant per Setting überschreibbar. Das ist das gleiche Pattern wie `process.status.allowed_values` in Plan 07 und braucht keinen neuen Mechanismus. Tabelle (c) ist Over-Engineering vor der Workflow-Engine. → **entschieden: b) Settings-Resolver** (2026-06-20).

3. **MCP-Cut: eigener `events_mcp` oder Tools im `process_mcp`?**
   - **a)** Eigener `events_mcp` (Port 8506, kind: tool). Sauber, weil Events polymorph an viele Entities hängen können (nicht nur Process) — über process_mcp anbinden würde die Domain-Trennung brechen.
   - **b)** Tools in `process_mcp` mit-bedienen. Kurzfristig spart Bootstrap, aber sobald Events an Project/Account/Contact hängen, ist der Name falsch.
   V1-Empfehlung: **a)** — eigener `events_mcp` analog zur Plan-07-Entscheidung. Vision §21 favorisiert klar getrennte MCPs. → **entschieden: a) eigener `events_mcp` (Port 8506)** (2026-06-20).

4. **Anker-Pflicht: muss ein Event immer einen Anker haben?**
   - **a)** Ja, `target_cls` und `target_id` sind NOT NULL und müssen beide gesetzt sein (anders als bei AiChat/Note, wo leerer Anker ok ist). Begründung: Events ohne Anker hätten keine Timeline-Heimat.
   - **b)** Nein, leerer Anker erlaubt für "tenant-globale" Events ("System-Wartung am Sonntag").
   V1-Empfehlung: **a)** — strikt verankert, "globale Tenant-Events" sind ein anderer Use-Case (Announcements), den wir später anders bauen. → **entschieden: a) Anker ist Pflicht** (2026-06-20).

5. **Listener-Reihenfolge `after_commit`:** der Auto-Event-Listener braucht die persistierten `EntityChange`-IDs für `source_ref`. Optionen:
   - **a)** Listener registriert sich nach Plan-04-Hook (`event.listen(Session, "after_commit", _auto_events_after_changes)`). SQLAlchemy ruft Listener in Registrierungsreihenfolge — solange `register_sync_listeners()` und `install_change_log_hooks()` zuerst laufen, ist alles ok. **Risiko**: Order-Sensitivität, unsichtbar wenn man die Registrierungsreihenfolge versehentlich umstellt.
   - **b)** Auto-Event-Listener konsumiert die Outbox in `audit.py` direkt, BEVOR `_drain` schreibt — dann braucht er die IDs nachträglich oder muss seine eigene Persistenz separat fahren. **Komplizierter.**
   - **c)** Auto-Event-Listener im after-commit-Drain selbst, als zweite Phase ("nach `EntityChange`-Insert direkt Events generieren in derselben Session"). **Bricht die DB-Branch-Trennung** (Events leben in tenant_db, EntityChange in logging_db).
   V1-Empfehlung: **a)** + ein expliziter Reihenfolge-Test im Smoke. Saubere Trennung, Reihenfolge dokumentiert. → **entschieden: a) eigener `after_commit`-Listener nach Plan-04, Smoke testet Reihenfolge** (2026-06-20).

6. **Default-Event-Typen:** welche Strings landen in der V1-Konvention (Doku, kein Validator)? Vorschlag:
   - `status_changed` (Auto, aus Process-Status-Wechsel)
   - `manual_entry` (Default für `log_event` ohne expliziten Typ)
   - `call_logged`, `mail_sent`, `meeting_scheduled` (manuell, vom Agent benutzt)
   - `note_added` — Vorsicht: kollidiert konzeptionell mit dem Anhängen einer `Note`-Entity. **V1-Empfehlung**: drauflassen, in V1 NICHT auto-erzeugt — manuelle Variante reicht.
   → **entschieden: Doku-Konvention, kein Validator. Liste = `status_changed`, `manual_entry`, `call_logged`, `mail_sent`, `meeting_scheduled`, `note_added`** (2026-06-20).

7. **Backfill historischer Daten:** soll beim Plan-08-Migrate ein einmaliger Backfill für vorhandene `EntityChange`-Einträge laufen (also für jeden bisherigen `core.process.status`-Wechsel ein Event nachschreiben)?
   - V1-Empfehlung: **Nein** — Backfill verzerrt `happened_at` (wir würden den `EntityChange.created_at` verwenden, was bei manuell gepatchten Migrations-Zeitpunkten Müll wäre). Auto-Erzeugung greift ab Deployment. Falls ein Tenant bestehende Daten als Events spiegeln will, kann man später ein Maintenance-Skript schreiben.
   → **entschieden: Nein, kein Backfill** (2026-06-20).

8. **`__change_log__` für Events selbst:** sollen Events selbst im Change-Log auftauchen? Vorschlag oben: ja (default). Risiko: Audit-über-Audit-Rauschen, wenn das System-Account viele Auto-Events erzeugt — der Change-Log wird voll. **Alternative**: `__change_log__ = False` für Auto-erzeugte, True für manuelle. **Geht aber nur über getrennten Pfad oder einen Suppression-Hook.** V1-Empfehlung: `__change_log__ = False` für die Klasse insgesamt (Events sind selbst Audit-artig — Audit-über-Audit ist Rauschen). Manuelle Korrektur passiert über soft-delete + neues Event, das genügt als Audit-Spur. → **entschieden: `__change_log__ = False` für die ganze Klasse** (2026-06-20).

## Aufwand

| Block | Schätzung |
|---|---|
| Entity-Model + Alembic-Migration | 1.5h |
| `lib/business_events.py` (Helper) + `actor`-/`trace_uid`-Integration aus tenant_context | 1h |
| `lib/audit_to_event.py` (Auto-Listener + Idempotenz-Check) | 2h |
| MCP-Server (eigener `events_mcp` mit 4 Tools) | 2h |
| Wiring (docker-compose, agent.py, start_local.sh) | 0.5h |
| Settings-Default für Auto-Rules + Resolver-Anbindung | 0.5h |
| Smoke-Skript mit allen Cases | 2h |
| Doku im Plan-File + VISION-Status-Update | 0.5h |

**Gesamt: ~10h.** Etwas größer als Plan 07, weil der Auto-Erzeugungs-Listener mit Idempotenz-Check + Reihenfolge-Garantie der heikelste Teil ist.

## Abhängigkeiten

- **Plan 01** (AiChat-Anker / Trace-Context-ContextVars) — **hart**: ohne `trace_uid` in den ContextVars wäre die `trace_uid`-Brücke leer. Welle 1 ist drin, also ok.
- **Plan 03** (Settings-Hierarchie) — **hart**, falls Offene Frage 2 Option (b): wir legen die Auto-Rules über den Settings-Resolver ab.
- **Plan 04** (Change-Log) — **hart**: die Auto-Erzeugung liest die persistierten `EntityChange`-Einträge per `source_ref`.
- **Plan 05** (MCP-Kind) — **hart**: `events_mcp` deklariert `kind: "tool"`.
- **Plan 06** (Debug-View) — **weich/Konsumenten-Seite**: Debug-View kann nach Plan 08 zu jedem Trace die zugehörigen fachlichen Events anzeigen — kein Pflicht-Hook in V1.
- **Plan 07** (Process) — **hart**: Auto-Erzeugung in V1 wird nur am Process-Status getriggert. Ohne Process-Entity (und ihr `status`-Feld) hätte die Whitelist nichts zu beobachten.

## Folge-Pläne, die hierauf aufbauen

- **Plan 09 (Vorschlag): Vorgangs-Timeline-UI** — kombiniert Change-Log + fachliche Events + (später) Sub-Chats in einem chronologischen Strom am `EntityOverlay`. Hängt evtl. mit dem Explorer-Plan (§18) zusammen.
- **Plan 10 (Vorschlag): Milestones** (§5) — Milestones haben Lifecycle-Events (`milestone_reached`), das ist ein zweiter Auto-Rule-Konsument.
- **Plan 11 (Vorschlag): Workflow-Engine V1** (§7) — Events sind die natürlichen Trigger ("wenn Event `status_changed` mit `new=wartet_auf_kunde` an einem Vorgang mit `kind=reklamation`, dann …").
- **Plan 12 (Vorschlag): Externe Event-Quellen** (§20) — Mail-Ingest und Kalender-Sync schreiben mit `source="mail_ingest"` etc. in dieselbe Tabelle.

## Umgesetzt am 2026-06-20

V1 wie geplant, alle 8 Offene Fragen entschieden wie empfohlen. Stack-Stand:

- **Entity** `lib/entities/tenant/business_event.py` — Klasse `BusinessEvent` (Tabelle `event`, Alias `core.event`), `__change_log__ = False`. Resource-Adapter, polymorpher Anker als NOT NULL.
- **Migration** `alembic/tenant/versions/20260620_0011_event.py` — Revision `tenant_0011 ← tenant_0010`. Vier Indizes (Timeline, trace_uid, type+happened, source+source_ref).
- **Helper** `lib/business_events.py` — `log_event()` (fuellt actor/trace aus tenant_context, Anker-Pflicht), `iter_auto_rules()` (Settings-Resolver), `render_title()`, `BUSINESS_EVENT_TYPES` Konvention.
- **Auto-Listener** `lib/audit_to_event.py` — `_after_commit_listener` liest neuen Snapshot `audit.COMMITTED_KEY` (Plan-04-Erweiterung, +12 Zeilen in `lib/audit.py:_drain`), materialisiert Events pro Whitelist-Treffer in tenant_db, idempotent via `source_ref=entity_change:<id>`. `install_event_hooks()` MUSS nach `install_change_log_hooks()` registriert werden.
- **Settings-Default** `PLATFORM_DEFAULTS["events.auto_rules.core.process"]` mit Status-Regel.
- **MCP** `mcp_servers/events_mcp/server.py` (Port 8506 extern, intern 8001) — Tools `event_log`, `event_get`, `event_list`, `event_delete`. Manifest mit `kind="tool"` und `event_type_conventions`. Eigener Service in `docker-compose.yml`, Eintrag in `lib/agent.MCP_ENDPOINTS`.
- **Wiring** Gateway-Bootstrap (`gateway/main.py:127`) ruft `install_event_hooks()` nach `install_change_log_hooks()`. Reihenfolge-Test im Smoke.
- **Smoke** `scripts/smoke_events.py` mit 10 Cases (alle 9 Plan-Cases + listener_order). Lauf gegen demo-Tenant grün.
- **Semantik-Sync** `BusinessEvent` zu `lib/semantic_sync.register_sync_listeners`-pairs hinzugefuegt — Events landen im Vector-Index.

Nebenher gefixt (waren bestehende Plan-07-Bugs, blockierten den Smoke):

- `mcp_servers/process_mcp/server.py` + `events_mcp/server.py`: `from __future__ import annotations` entfernt — FastMCP 1.12.4 stolpert ueber String-Annotationen.
- `update_process(... patch: dict | None)` → `dict = {}`, dito `event_log(... data)`.

Commit: kommt mit dieser Plan-08-Welle.
