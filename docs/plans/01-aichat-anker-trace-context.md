# Plan 01 — AiChat polymorpher Anker + Trace-Context-Infrastruktur

**Welle 1, Feature 1. Vision-Refs: §2 (trace_uid-Brücke), §10 (Sub-Chat-Anker), §18 (Chat ↔ View).**

## Ziel

Zwei Mini-Bausteine, die alle nachfolgenden Wellen einfacher machen:

1. **`AiChat` bekommt einen polymorphen Anker** (`target_cls` / `target_id`). Damit kann ein Chat (Top-Level oder Sub) explizit "über einer Resource" laufen — Vorgang, View, Document, Sub-Agent-Task. Voraussetzung für §10 sauberere Sub-Chats und §18 Chat ↔ View.
2. **Zentraler Trace-Context als ContextVar.** `trace_uid` und Actor-Identität werden pro Request gesetzt, ohne dass jeder Aufrufpfad sie weiterreichen muss. Voraussetzung für Plan 04 (Change-Log-Hook braucht trace_uid + actor) und für Sub-Agent-Lifecycle-Events (Plan 02).

## Schnittweise — was NICHT reinkommt

- **Kein fachliches Event-Modell** (§2) — kommt in Welle 3, dann mit `trace_uid`-Spalte.
- **Kein UI-Change** im Chat-Header / Resource-Sicht — der Anker wird nur persistiert. Anzeige kommt mit Explorer-Iteration.
- **Keine Auto-Migration alter Chats** — neue Chats setzen den Anker, alte bleiben unverankert.
- **Kein Result-Contract** — das ist Plan 10 (Welle 4).

## Datenmodell

### `tenant_db.ai_chat` — zwei neue Spalten

```python
target_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
target_id: Mapped[int]  = mapped_column(Integer, nullable=False, default=0)
```

- Leerer `target_cls` = unverankerter Chat (Default für freie Konversationen).
- Composite-Index `(target_cls, target_id)` für die Reverse-Query "alle Chats über dieser Resource".
- Keine FK — wir haben generell keine FKs (`lib/mixins.py`-Doc).

### Migration

Neue Alembic-Revision `20260620_0008_aichat_anker.py` (tenant-Branch):
- `op.add_column("ai_chat", sa.Column("target_cls", sa.String(64), nullable=False, server_default=""))`
- `op.add_column("ai_chat", sa.Column("target_id", sa.Integer, nullable=False, server_default="0"))`
- `op.create_index("ix_ai_chat_target", "ai_chat", ["target_cls", "target_id"])`

## Code-Touchpoints

### `lib/tenant_context.py` — Trace-Context erweitern

Existiert schon mit `set_tenant`, `set_user`, `set_request_id`. Hinzufügen:

```python
_trace_uid: ContextVar[str | None] = ContextVar("wai_trace_uid", default=None)
_actor_type: ContextVar[str] = ContextVar("wai_actor_type", default="human")
_agent_name: ContextVar[str] = ContextVar("wai_agent_name", default="")

def set_trace_uid(uid: str | None) -> None: ...
def get_trace_uid() -> str | None: ...
def set_actor(actor_type: str, agent_name: str = "") -> None: ...
def get_actor() -> tuple[str, str]: ...
```

`actor_type` ∈ `{"human", "ai", "system"}`. Im Gateway-Default `"human"`. Wenn ein Agent loslegt, wird auf `"ai"` + `agent_name` umgestellt. Sub-Agent-Spawn erbt von ihrem `task` Context via `copy_context()` (siehe Plan 02).

### `lib/entities/tenant/ai_chat.py` — neue Spalten

Sechs neue Zeilen, oberhalb der bestehenden Felder.

### `gateway/main.py` — Trace-Context setzen

Im Chat-Send-Pfad (dort wo `EventEmitter` initialisiert wird): direkt nach `trace_uid = new_trace_uid()` ein `set_trace_uid(trace_uid)`. Plus `set_actor("human", "")` zu Beginn jedes Requests (im Auth-Middleware-Bereich, falls vorhanden).

Beim Eintritt in den Agent-Code: `set_actor("ai", "manager")`.

### `gateway/ui_chat.py` — Anker beim Chat-Create

Neue Chats akzeptieren optional `target_cls` / `target_id` (Query- oder Body-Param). Default leer. Persistiert im `AiChat`-Insert.

### `agents/manager/agent.py` — Anker für Sub-Chats

Wenn der Manager via `run_sales_support` (Zeile 369) delegiert: der spawnende Code setzt den Anker des neuen Sub-`AiChat` auf den Parent-Resource-Anker (Sub erbt Anker des Parents), falls einer existiert. Sonst leer.

## UI-Punkte

- **Keine** in dieser Iteration. Der Anker ist nur Datenfeld.
- Nächste Iteration (Explorer V1 oder Resource-Overlay-Tab) liest `ai_chat WHERE target_cls=? AND target_id=?` für den "Chats"-Tab pro Resource.

## Tests

- Migration up/down auf leerer DB.
- `AiChat`-Create mit Anker persistiert sauber.
- ContextVar-Reset zwischen Requests (asyncio-Task-Isolation prüfen).
- Sub-Chat erbt Anker, wenn Parent einen hat.

## Offene Fragen

- **`target_cls`-Validierung**: streng (`is_valid_alias()` erzwingen) oder permissiv (jeder String erlaubt)? Tendenz: streng, mit klarem Fehler beim Insert.
  → **entschieden (2026-06-20):** streng. Wir bauen einen `validate_target(cls_alias, target_id)`-Helper in `lib/polymorphic.py` und benutzen ihn im `AiChat`-Insert-Pfad. Leerer `target_cls` ("") bleibt erlaubt = unverankerter Chat. Wenn das beim Bauen friktional wird, rudern wir zurück. Andere Entities (`Task`, `Note`, …) werden in dieser Iteration **nicht** nachgezogen.
- **Multiple Targets pro Chat?** Z.B. Chat über zwei Vorgänge gleichzeitig. Vision sagt 1:1 (`§24` "Chat-Anker = 1:1"). Bleibt 1:1, Mehrfach-Bezüge laufen über `ChatArtifact` (M:N).
  → **entschieden (2026-06-20):** 1:1 wie Vision §24. M:N-Bezüge laufen über `ChatArtifact`.
- **Actor-Default bei System-Jobs** (Cron, Reminder): `"system"` ja, aber wer setzt das? Vermutlich ein zentraler `with_actor("system", "cron")` Kontextmanager.
  → **entschieden (2026-06-20):** **kein** eigener `"system"`-Actor-Typ. `actor_type` Enum schrumpft auf `{"human", "ai"}`. Cron/Reminder/Webhook-Worker laufen unter einem per-Tenant **technischen User-Account** (Audit-Trail uniform: "User `cron@tenant` hat X getan"). Folgearbeit außerhalb Plan 01: `User`-Modell bekommt später ein `kind`-Flag, damit Admin-Views Bot- von Mensch-Accounts trennen können; Seed legt einen Cron-User pro Tenant an, sobald der erste Cron-Aufrufer gebaut wird.
- **Sub-Agent erbt Anker — immer?** Oder kann der Manager bewusst einen anderen Anker setzen ("dieser Sub-Chat geht über *anderes Dokument*")? Tendenz: Default erben, explizit überschreibbar.
  → **entschieden (2026-06-20):** Default erben (kommt eh kostenlos via `copy_context()`), explizit überschreibbar. **API-Form wird in Plan 02 festgeklopft**, nicht hier — sonst bauen wir an einer Sub-Spawn-Signatur, die wir bei Plan 02 sowieso anfassen.

## Scope-Anpassung nach Durchsprache (2026-06-20)

Der ursprüngliche Punkt "Manager-Agent-Anker-Vererbung" unter Code-Touchpoints (`agents/manager/agent.py` Z.369) wandert **raus aus Plan 01** und ins Plan 02 (Sub-Agent-Lifecycle), wo der ganze Sub-Spawn-Pfad (`copy_context()`, Result-Contract-Vorbereitung, Anker-Vererbung) ohnehin landet. Plan 01 bleibt damit pure Infrastruktur: Spalten + ContextVars + Gateway-Set + Validator-Helper.

## Aufwand

- Migration + AiChat-Model: 10 min
- ContextVar-Erweiterung: 15 min
- Gateway-Integration: 30 min
- Manager-Agent-Anker-Vererbung: 20 min
- Tests: 30 min

**Gesamt: ~1.5h reine Arbeit, plus Diskussion vorab.**

## Umgesetzt am 2026-06-20

- Alembic-Revision: `tenant_0008` (`alembic/tenant/versions/20260620_0008_aichat_anker.py`) — fügt `target_cls` (`String(64)`, default `""`) + `target_id` (`Integer`, default `0`) auf `ai_chat` hinzu, dazu Composite-Index `ix_ai_chat_target`. Down-Revision: `tenant_0007`.
- `lib/entities/tenant/ai_chat.py` — zwei neue Mapped-Spalten am Ende der Klasse, Docstring um Anker-Absatz erweitert.
- `lib/polymorphic.py` — neuer Helper `validate_target(cls_alias, target_id)`. Streng: Empty-Anker (`""`/`0`) ok, sonst Alias muss in `_alias_to_cls` und `target_id > 0` sein; XOR-Mismatch wird erkannt. Andere Entities (`Task`, `Note`, …) sind in dieser Iteration **nicht** mit nachgezogen — siehe Schnittweise.
- `lib/tenant_context.py` — drei neue `ContextVar`s (`_trace_uid`, `_actor_type` Default `"human"`, `_agent_name`) plus Helper `set_trace_uid` / `get_trace_uid` / `set_actor` / `get_actor`. `set_actor` validiert gegen `{"human", "ai"}`.
- `gateway/main.py` — Import von `validate_target` und `set_trace_uid`; `NewChatRequest` bekommt optional `target_cls` + `target_id`; `create_chat` validiert + persistiert den Anker (422 bei ungültigem Anker); `_run_chat_streaming` setzt `set_trace_uid(trace_uid)` direkt nach der Trace-Erzeugung.
- `agents/manager/agent.py` — `set_actor("ai", "manager")` als erste Zeile in `chat()`. ContextVar greift per `asyncio.create_task` automatisch ohne explizites `copy_context()`-Boilerplate.
- **Bewusst raus**: Sub-Chat-Anker-Vererbung im Manager (`run_sales_support`-Pfad, Z.369) — wandert in Plan 02, wo der Sub-Spawn-Pfad sowieso angefasst wird.
- **Tests**: kein automatisches Test-Setup vorhanden, daher nur Smoke-Test via `python3 -c` durchgeführt (Imports, `validate_target` mit gültigen + ungültigen Aliasen, `set_actor` mit `"system"` blockt korrekt, Round-Trip von Trace-UID + Actor).
- **Migration auf `tenant_demo` ausgeführt** am 2026-06-20: `alembic -c alembic-tenant.ini -x tenant_slug=demo upgrade head` (`tenant_0007 → tenant_0008`), Schema verifiziert (`\d ai_chat` zeigt `target_cls`, `target_id`, Index `ix_ai_chat_target`).
- Commit: siehe `git log --grep "Plan 01"`.

### Vision-Status

- §10 (Nested Chats / Sub-Chats): bleibt **teilweise** — Anker ist jetzt persistierbar, Sub-Chat-Result-Contract und UI fehlen weiter.
- §18 (Explorer): bleibt **fehlt komplett** — Anker ist Vorarbeit, kein Explorer-Code in dieser Iteration.
