# Plan 07 — Vorgang (Process) V1

**Welle 3, Feature 1. Vision-Ref: §1 (Projekte und Vorgänge), berührt §2 (Events), §10/§18 (AiChat-Anker), §21 (MCP-Pattern).**

## Ziel

Neue Tenant-Entität für die **kleinere, anlassgetriebene Arbeitseinheit** ("Kunde meldet sich", "Reklamation 4711", "TÜV-Abnahme für Produkt Y") — semantisch klar getrennt von `Project`, optional unter ein Projekt einhängbar. Dient als **fachlicher Daten-Anker** für die folgenden Vision-Features (Fachliche Events §2, Workflows §7, Externe Integrationen §20, Explorer-Views §18).

## Schnittweise — V1 vs. spätere Iterationen

**V1 (dieser Plan):**
- Tenant-Entität `Process` mit Stammfeldern (Name, Beschreibung, Status, Owner, Assignee, optional Projekt-Ref, optional CRM-Account-Ref, optional parent_process-Ref).
- Alembic-Migration in der Tenant-DB-Branch.
- Polymorpher Anker funktioniert in beide Richtungen out-of-the-box (anhängen *an* Process via `target_cls="core.process"` für bestehende Note/Comment/Attachment/Task/AiChat — funktioniert automatisch, weil das alles polymorph ist).
- Automatik durch bestehende Welle-1/2-Infrastruktur: Change-Log (Plan 04), Semantic-Sync (vorhanden), Settings-Resolver (Plan 03).
- Neuer MCP `process_mcp` (Port 8002, `kind: "tool"`) mit Basis-CRUD-Tools (`create_process`, `get_process`, `list_processes`, `update_process`, `link_to_project`, `archive_process`).
- Generische `EntityOverlay`-Integration plus Chat-Anker (über `AiChat.target_cls/target_id`, Plan 01 — funktioniert sofort).

**Spätere Iterationen (eigene Pläne):**
- **Fachliche Events** am Vorgang (§2) — eigener Plan, hängt an diesem.
- **Vorgangs-Listing-UI** mit Filtern/Status-Spalten — kommt mit Explorer V1 (§18).
- **Vorgangs-Visualisierung** (Timeline, Burndown, §11) — eigener Plan.
- **Workflow-Bindung** (§7) — der `kind`/`workflow_id`-Hook ist im Schema vorgesehen, aber leer in V1.
- **`explorer_scope`-Marker** als globaler Mechanismus — eigener Mini-Plan, der dann auch retroaktiv allen bestehenden Entities das Label gibt. In Plan 07 nur als Notiz: Process bekommt `explorer_scope = "fachlich"`, sobald der Marker existiert.

## Schnittweise — was NICHT in V1 reinkommt

- **Keine Milestones** (§5) — eigener Plan, hängt an Vorgang.
- **Keine Memberships** über Membership-Tabelle — nur `owner_user_id` und `assignee_user_id` als nackte Refs. Mehrere Beteiligte später, vermutlich polymorph oder über eine Beteiligten-Mini-Tabelle.
- **Kein dediziertes Vorgangs-Dashboard** — Detail-Sicht via generisches `EntityOverlay`. Listen-Sicht kommt mit Explorer.
- **Kein Workflow-Zuordnungs-Auto-Mechanismus** — V1 hat nur ein freies `kind`-Stringfeld, aber keine Workflow-Engine dahinter.
- **Keine UI für Sub-Vorgang-Anzeige** — `parent_id` existiert im Schema, eine Baumansicht im UI kommt erst, wenn Explorer da ist.
- **Keine Status-Lifecycle-Validierung** — `status` ist Freitext-String mit dokumentierten Default-Werten, Übergangsregeln kommen erst, wenn Workflow-Engine existiert.
- **Kein eigener REST-Resource-Endpoint im Gateway** — Zugriff geht über den MCP. Wenn das UI später direkter sprechen muss, kommt das mit dem jeweiligen UI-Plan.

## Code-Name-Entscheidung

**Vorschlag: `Process` als Class-Name, `core.process` als register_entity-Alias.**

Begründung:
- Repo-Konvention: Class-Namen englisch (`Project`, `Task`, `Contact`, `Account`, `Note`, `Comment`, `Attachment`), Konversation deutsch. `Vorgang` als Class-Name würde aus der Reihe fallen.
- `Process` ist semantisch nah am Vision-Begriff und kollidiert nicht mit bestehenden Tenant-Klassen (`Project` ist der wichtigste Nachbar).
- OS-Process-Konnotation ist im Domain-Kontext "Tenant-Entität" nicht verwechslungsgefährlich; im Code stehen Imports immer mit `from lib.entities.tenant.process import Process`, kein Konflikt.
- Alternative `Case` wäre auch tragbar, aber legal-/support-konnotiert. `Process` bleibt domänen-neutral.

→ **Offene Frage 1** im Abschnitt unten — vor Code-Start mit User bestätigen.

## Datenmodell

### Tabelle `process` (Tenant-DB)

```text
id                int PK            -- aus IdMixin
created_at        datetime          -- aus TimestampMixin
updated_at        datetime          -- aus TimestampMixin
is_deleted        bool default F    -- aus SoftDeleteMixin

name              str(200) NOT NULL
description       text default ""   -- Freitext, primärer Bedeutungsträger (semantisch indexiert)
status            str(40) default "neu"
                  -- Default-Werte (V1, freier String): "neu" | "in_arbeit" | "wartet_auf_kunde" |
                  --                                    "wartet_intern" | "abgeschlossen" | "abgebrochen"
priority          str(20) default "normal"
                  -- "niedrig" | "normal" | "hoch" | "kritisch"
kind              str(40) default ""
                  -- optionaler Typ-Tag ("reklamation", "tuev_abnahme", …),
                  -- Vorbereitung für Workflow-Bindung §7, in V1 nur Freitext

owner_user_id     int default 0     -- nackte Ref auf admin_db.user (Repo-Konvention: keine FK)
assignee_user_id  int default 0     -- nackte Ref, kann == owner sein, default 0 = nicht zugewiesen

project_id        int default 0     -- nackte Ref auf tenant_db.project, 0 = freistehend
parent_id         int default 0     -- nackte Self-Ref für Sub-Vorgänge, 0 = top-level
customer_cls      str(80) default ""-- polymorpher Anker auf Kunden-Entity (z.B. "crm.account"), "" = keine Bindung
customer_id       int default 0     -- polymorpher Anker-Part, 0 = keine Bindung

due_at            datetime null     -- optionales Zieldatum
closed_at         datetime null     -- Zeitpunkt des Statuswechsels nach "abgeschlossen"/"abgebrochen"
```

**Indices:**
- `(is_deleted, status)` — Listen-Queries "alle offenen".
- `(project_id, is_deleted)` — "alle Vorgänge zu Projekt X".
- `(assignee_user_id, status)` — "meine offenen Vorgänge".
- `(customer_cls, customer_id, is_deleted)` — "alle Vorgänge zu Kunde X" (polymorph).
- `(parent_id)` — Sub-Vorgangs-Lookup.

**Bewusst keine FK-Constraints** (Repo-Konvention, siehe CLAUDE.md). Polymorphes Anhängen anderer Entities funktioniert automatisch über deren `target_cls="core.process"` / `target_id=process.id`.

### Migration

Pfad: `alembic/tenant/versions/YYYYMMDD_0010_process.py`.

- `revision = "tenant_0010"`, `down_revision = "tenant_0009"`.
- `op.create_table("process", …)` mit obigen Spalten.
- Vier Indices wie oben.
- Downgrade: `op.drop_table("process")`.

## Code-Touchpoints

### Neu

- `lib/entities/tenant/process.py` — `Process(TenantBase, BaseMixin)` mit `@register_entity("core.process")`. Analog zu `lib/entities/tenant/project.py:1-25`, erweitert um die Felder oben.
- `alembic/tenant/versions/YYYYMMDD_0010_process.py` — siehe Datenmodell.
- `mcp_servers/process_mcp/` — neuer MCP-Server-Ordner mit:
  - `server.py` — FastMCP-Server analog `mcp_servers/crm_mcp/server.py:1-200`, Port 8002.
  - `__init__.py`.
  - `Dockerfile` / `pyproject.toml` falls dem MCP-Ordner-Pattern entsprechend (am bestehenden CRM-MCP orientieren).
  - Manifest mit `kind: "tool"`, exponierte Tools, verwaltete Entität `core.process`.
- Tests:
  - `tests/lib/entities/test_process.py` — Create/Update/Soft-Delete, polymorpher Anker, Defaults.
  - `tests/mcp_servers/test_process_mcp.py` — Tool-Calls Smoke.

### Berührt (sehr leichte Änderungen)

- `lib/entities/tenant/__init__.py` — `Process` re-export, damit der Import-Side-Effect (`@register_entity`) ausgelöst wird, sobald irgendwo Tenant-Models importiert werden. Analog zu Project.
- `docker-compose.yml` (falls die MCP-Server dort gelistet sind — am CRM-MCP-Eintrag orientieren).
- `lib/agent.py` / wo immer die MCP-Server registriert werden — `process_mcp` in die Capability-Discovery aufnehmen (Detail beim Implementieren am bestehenden CRM-MCP-Eintrag orientieren).
- Seed-Skript (`scripts/seed_tenant_demo.py` falls vorhanden) — 2-3 Demo-Vorgänge anlegen, einer mit `project_id`, einer mit `account_id`, einer frei. Hilft im Debug-View die neue Entität sofort zu sehen.

### Auto-Integration (kein eigener Code nötig)

- **Change-Log (Plan 04):** `lib/audit.py:31` Hooks greifen automatisch, da `Process` von `BaseMixin` erbt und nicht `__change_log__ = False` setzt. Alle Feld-Diffs landen in `logging_db.entity_change`.
- **Semantic-Sync:** `lib/semantic_sync.py:34` `register_sync_listeners()` greift automatisch — `name + description + kind + status` werden zum Abstract. **Eine Sache zu prüfen beim Implementieren:** wenn der Sync-Listener pro Entity-Typ angemeldet werden muss (statt generisch über BaseMixin), dann den Process explizit dazuhängen.
- **Settings-Resolver (Plan 03):** Niemand muss was tun — Settings können später per `entity_type="core.process"` oder per konkreter `entity_id` gesetzt werden, der Resolver findet das.
- **AiChat-Anker (Plan 01):** `AiChat.target_cls="core.process"`, `target_id=<id>` funktioniert sofort — kein neuer Code nötig.

## MCP-Anbindung: `process_mcp`

Analog `mcp_servers/crm_mcp/server.py`. Manifest:

- `name: "process_mcp"`
- `kind: "tool"` (Plan 05)
- `description: "Verwaltung von Vorgängen (anlassgetriebene Arbeitseinheiten)"`
- `entities: ["core.process"]`
- `dependencies: []` (für V1; später ggf. `core.project`, `crm.account` als Reads)

**Tools (V1):**

- `create_process(name, description?, kind?, project_id?, customer_cls?, customer_id?, parent_id?, assignee_user_id?, priority?, due_at?) -> {id}`
- `get_process(id) -> {…}`
- `list_processes(filter?: {status?, assignee_user_id?, project_id?, customer_cls?, customer_id?, kind?}, limit?, offset?) -> [{…}]`
- `update_process(id, patch: {name?, description?, status?, priority?, kind?, assignee_user_id?, due_at?, ...}) -> {ok}` — wenn `status` im Patch ist, dieselbe `closed_at`-Logik wie `set_status`.
- `link_to_project(process_id, project_id) -> {ok}`
- `link_to_customer(process_id, customer_cls, customer_id) -> {ok}` — validiert `customer_cls` über `lib/polymorphic.validate_target`.
- `archive_process(id) -> {ok}` — Setzt `is_deleted=True` über soft delete.

**Status-Setter-Komfort-Tools (optional, aber bringen viel):**

- `set_status(id, status) -> {ok}` — validiert gegen `settings.resolve("process.status.allowed_values", entity_cls="core.process", entity_id=id)`; wenn `status in ("abgeschlossen","abgebrochen")`, automatisch `closed_at` setzen.

**Setting-Default (V1):**

- `process.status.allowed_values` → `["neu","in_arbeit","wartet_auf_kunde","wartet_intern","abgeschlossen","abgebrochen"]` als Plattform-Default in `settings`-Seed/Schema.

Der Agent kann diese Tools direkt rufen, jeder Call landet im Change-Log (über die generische Hook-Mechanik), jede Status-Änderung kann später automatisch ein fachliches Event erzeugen (kommt mit dem Events-Plan §2).

## UI-Punkte

**V1 minimal:**
- `interface/components/overlays/EntityOverlay.tsx` rendert `Process` generisch — Felder als Form, Tabs **"Verlauf"** (Change-Log, kommt aus Plan 04), **"Chats"** (`AiChat where target_cls='core.process' and target_id=?`, kommt aus Plan 01).
- Kein eigener `/processes`-Route in der Next-App in V1 — der Vorgang wird primär aus dem Chat heraus erstellt/bearbeitet (Agent ruft MCP-Tools), und im EntityOverlay angezeigt.

**Bewusst später (eigene Pläne):**
- Listen-Page über alle Vorgänge → Explorer (§18).
- Timeline-Visualisierung am Vorgang → mit Fachliche-Events-Plan + Visualisierungs-Plan.
- Sub-Vorgangs-Baum-Anzeige → mit Explorer.

## Tests

**Mindest-Cases:**

1. **Schema/Migration:**
   - `tenant_0010` upgrade/downgrade greift sauber gegen eine frische Test-Tenant-DB.
   - Defaults werden gesetzt (`status="neu"`, `priority="normal"`, alle FK-IDs default 0).

2. **Entity-Verhalten:**
   - Create + Read.
   - Update von `status` → `closed_at` wird gesetzt, wenn `status` in `{abgeschlossen, abgebrochen}`.
   - Soft-Delete via `archive_process` → `is_deleted=True`, taucht nicht in `list_processes` auf.
   - Polymorphes Anhängen einer Note an Process funktioniert (Note.target_cls="core.process", target_id=<id>).
   - Nesting: `parent_id` kann auf einen anderen Process zeigen, `list_processes(filter={parent_id: X})` findet Kinder.

3. **Change-Log-Integration:**
   - Update auf `description` erzeugt einen `EntityChange`-Eintrag mit `target_cls="core.process"`, `field_diffs=[{field: "description", old: …, new: …}]`.
   - Create erzeugt `change_type="create"`, Delete `change_type="soft_delete"`.

4. **AiChat-Anker:**
   - Ein `AiChat` mit `target_cls="core.process", target_id=<id>` lässt sich anlegen, der Process-Lookup über `target_cls/target_id` findet ihn (validiert über `lib/polymorphic.validate_target`).

5. **Semantic-Sync:**
   - Nach Create+Commit existiert ein `semantic_fassade`-Eintrag für den Process; nach Update der `description` ändert sich `content_hash`.

6. **MCP-Tools (Smoke):**
   - Jedes Tool aus dem Manifest ist erreichbar und gibt valid JSON zurück; `create_process` → `get_process` → `update_process` → `archive_process` Happy-Path läuft.

7. **Settings-Hook (Optional, falls schnell):**
   - `settings.resolve("process.default_priority", entity_cls="core.process", entity_id=…)` greift den Plattform-Default — kein Crash bei leerer Setting-Tabelle.

## Offene Fragen

1. **Code-Name** — `Process` (vorgeschlagen) vs. `Case` vs. `Vorgang` direkt? → **entschieden: `Process`** (Class-Name englisch konform zu Repo-Konvention, Alias `core.process`).
2. **`status`-Default-Werte** — die fünf vorgeschlagenen Werte (`neu/in_arbeit/wartet_auf_kunde/wartet_intern/abgeschlossen/abgebrochen`) als rein dokumentarische Konvention reichen für V1, oder soll ein Setting-Key `process.status.allowed_values` einen Validator triggern? V1-Empfehlung: nur Doku, kein Validator. → **entschieden: Setting-Key `process.status.allowed_values` + Validator.** Default-Liste wird im Settings-Schema als Plattform-Default abgelegt; `update_process` / `set_status` lehnen Werte außerhalb der Liste mit Fehler ab. Workflow-Engine später überschreibt das auf Tenant-/Workflow-Ebene.
3. **Status `closed_at`-Automatik** — automatisch im `set_status`-Tool setzen ist okay, aber soll das auch ein generischer SQLAlchemy-Hook am Model selbst sein (greift dann auch, wenn jemand direkt am Session-Objekt schreibt)? V1-Empfehlung: nur im Tool, am Model-Hook ist Over-Engineering bevor wir mehrere Schreib-Pfade haben. → **entschieden: nur im Tool** (in `set_status` und in `update_process`, wenn die Patch-Map `status` enthält). Kein Model-Hook in V1.
4. **`account_id` als nackte Ref vs. polymorpher Anker** — V1 ist `account_id` als nackte Ref (CRM-Account-spezifisch). Wenn später auch B2C-Kontakte direkt am Vorgang hängen sollen, müsste das polymorph werden (`customer_cls` + `customer_id`). V1-Empfehlung: nackte Ref, weil heute alle Vorgänge gegen Accounts laufen. → **entschieden: polymorph `customer_cls` + `customer_id`** (statt `account_id`). Begründung: B2C-Kontakte/Leads als Vorgangs-Kunden sind absehbar, lieber jetzt richtig modellieren als später migrieren. Index `(customer_cls, customer_id, is_deleted)` statt `(account_id, is_deleted)`. Helper `link_to_customer(process_id, customer_cls, customer_id)` ersetzt `link_to_account`.
5. **`process_mcp` als eigener MCP oder Erweiterung von `crm_mcp`?** — Vision §21 favorisiert klar getrennte MCPs pro Domäne. Vorgang ist eigene Domäne (anlassgetrieben, nicht CRM-spezifisch), Kunden-/Account-Bindung ist nur eine von vielen. V1-Empfehlung: eigener MCP. → **entschieden: eigener `process_mcp`** (Port 8002, `kind: "tool"`).
6. **Seed-Daten** — sollen 2-3 Demo-Vorgänge im Seed angelegt werden, oder bleibt der Tenant initial leer und der Demo-Lauf erzeugt sie über Chat? V1-Empfehlung: Seed-Eintrag, damit der Debug-View und das künftige Listing direkt was zu zeigen haben. → **entschieden: ja, 2–3 Demo-Vorgänge** (einer mit `project_id`, einer mit `customer_cls="crm.account"` + `customer_id`, einer frei).
7. **`explorer_scope`-Marker jetzt schon einführen?** — Plan 07 könnte den Marker-Mechanismus mit anlegen (eine Zeile in `lib/polymorphic.register_entity`, ein Enum). Wenn ja, müsste er retroaktiv allen bestehenden ~25 Entities zugeordnet werden. V1-Empfehlung: nicht in diesem Plan — separater Mini-Plan, der mit dem Explorer-Plan gepaart läuft. Process wird im Code mit einem Kommentar markiert ("explorer_scope=fachlich, sobald Marker existiert"). → **entschieden: nicht in diesem Plan** — separater Mini-Plan, Process bekommt nur einen Code-Kommentar als Platzhalter.

## Aufwand

| Block | Schätzung |
|---|---|
| Entity-Model + Alembic-Migration | 1.5h |
| MCP-Server (`process_mcp`) mit Basis-Tools | 3h |
| Test-Suite (Entity, Hooks, MCP-Smoke) | 2h |
| Seed-Eintrag + Doku im Header | 0.5h |
| Manifest/Capabilities-Wiring (`process_mcp` in Agent-Discovery, docker-compose) | 1h |
| Smoke gegen Debug-View (Plan 06) — sieht der Detail-View die Tool-Calls? | 0.5h |

**Gesamt: ~8.5h.** Mittleres Stück — der größte Posten ist der MCP-Server, weil ein neuer MCP-Bootstrap-Aufwand hat (auch wenn er klein bleibt).

## Abhängigkeiten

- **Plan 01** (AiChat-Anker) — **weich/hart**: für den "Chats"-Tab im Process-Overlay nötig, aber Process selbst kommt auch ohne.
- **Plan 02** (Sub-Agent-Lifecycle) — **keine direkte Abhängigkeit**, aber wenn der Agent über einen Sub-Agent (z.B. `sales_support`) Vorgänge anlegt, läuft das Lifecycle-Event automatisch.
- **Plan 03** (Settings-Hierarchie) — **weich**: Process kann von Day 1 Settings konsumieren, aber V1 nutzt keine.
- **Plan 04** (Change-Log) — **hart**: Audit-Hook ist die Voraussetzung dafür, dass jede Process-Änderung im Verlaufs-Tab landet — ohne Plan 04 wäre der Verlaufs-Tab leer.
- **Plan 05** (MCP-Kind) — **hart**: `process_mcp` muss `kind: "tool"` deklarieren, damit der Debug-View ihn korrekt einordnet.
- **Plan 06** (Debug-View) — **weich/Konsumenten-Seite**: Debug-View zeigt automatisch die neuen Tool-Calls und Change-Log-Einträge, sobald Process live ist.

## Folge-Pläne, die hierauf aufbauen

- **Plan 08 (Vorschlag): Fachliche Events am Vorgang** (§2) — `tenant_db.event` mit `trace_uid`, Auto-Erzeugung aus Change-Log-Einträgen für bestimmte Felder (z.B. `status`).
- **Plan 09 (Vorschlag): Milestones** (§5) — hängen polymorph an Vorgang/Projekt.
- **Plan 10 (Vorschlag): Workflow-Engine V1** (§7) — `kind`-Tag am Process bindet einen Workflow, AI nutzt die Beschreibung als Kontext.

---

## Umgesetzt am 2026-06-20

V1 von Plan 07. Dateien:

- **Entity:** `lib/entities/tenant/process.py` — `Process(BaseMixin, TenantBase)`, Alias `core.process`. Polymorpher Kunden-Anker `customer_cls` + `customer_id` (statt der ursprünglich vorgesehenen `account_id`, siehe Offene Frage 4). Resource-Adapter (`get_resource_*`) für die Semantic-Schicht.
- **Migration:** `alembic/tenant/versions/20260620_0010_process.py` — `tenant_0010 ← tenant_0009`. Fünf Indices (`ix_process_status_open`, `ix_process_project`, `ix_process_assignee`, `ix_process_customer`, `ix_process_parent`).
- **Paket-Re-Export:** `lib/entities/tenant/__init__.py` (Import + `__all__`), plus Process in `lib/semantic_sync.register_sync_listeners` pairs → Auto-Sync der Fassade.
- **Settings-Defaults (Plan 03):** `lib/settings.PLATFORM_DEFAULTS` ergänzt um `process.status.allowed_values` und `process.status.closed_values`. Validator sitzt im MCP-Tool, kein Model-Hook (Offene Frage 3).
- **MCP-Server:** `mcp_servers/process_mcp/{__init__.py,server.py}` — Port 8505 extern (Repo-Konvention, statt der im Plan genannten 8002), intern 8001. Tools: `manifest`, `create_process`, `get_process`, `list_processes`, `update_process` (mit Status-Validator + closed_at-Automatik), `set_status`, `link_to_project`, `link_to_customer`, `archive_process`, `allowed_status_values`. Whitelist `_PATCHABLE_FIELDS` verhindert versehentliche Patches auf owner/created_at/is_deleted.
- **Wiring:** `docker-compose.yml` (neuer Service `process_mcp`, Port-Mapping 8505:8001) und `lib/agent.MCP_ENDPOINTS` (Eintrag `("process", "http://process_mcp:8001/sse")`).
- **Seed:** `scripts/seed_tenant_demo.py` — idempotent, legt Demo-Projekt + Demo-Account + drei Vorgänge an (1× am Projekt, 1× am Account polymorph, 1× freistehend). Aufruf in `scripts/start_local.sh` ergänzt.
- **Smoke:** `scripts/smoke_process.py` — Mindest-Cases: Create+Read+Defaults, Change-Log-Eintrag bei Update, Status-Validator + closed_at-Automatik (mit Setzen + Zurücksetzen), polymorpher Note-Anker, parent_id-Nesting + `list_processes(parent_id=)`-Filter, AiChat-Anker, Semantic-Fassade + Rebuild-bei-Description-Change, Settings-Resolver-Fallback, MCP-Tool-Happy-Path. Läuft per `docker compose exec -T gateway python scripts/smoke_process.py`.
- **Vision:** §1 Status auf "Vorgang als V1 vorhanden" gestellt, Code-Name-Frage als entschieden markiert.

**Bewusst nicht umgesetzt** (kommt mit eigenen Plänen):
- Fachliche Events / Vorgangs-Timeline-UI / Listen-Page über Explorer / Milestone-Hängung / Workflow-Engine — Folge-Pläne 08+ wie oben skizziert.
- `explorer_scope`-Marker — separater Mini-Plan; in der Entity nur als Code-Kommentar vermerkt.
- README-Refresh in `mcp_servers/README.md` und `agents/README.md` (Port-Tabelle 8505) — vom Skope ausgenommen; war beim Repo-Stand schon nicht aktuell.
