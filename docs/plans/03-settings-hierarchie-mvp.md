# Plan 03 — Settings-Hierarchie MVP

**Welle 1, Feature 3. Vision-Ref: §27.**

## Ziel

Eine generische Setting-Mechanik mit zentralem Resolver, sodass alle künftigen "soll X als Default Y oder Z?"-Fragen über eine einzige API laufen. In dieser Iteration nur **zwei** der vier Schichten echt: Plattform + Tenant. Entity und Chat-Session als Stubs.

## Schnittweise — was NICHT reinkommt

- **Entity-Settings + Chat-Session-Settings** sind nur als Spalten-Stub angelegt; Resolver akzeptiert die Parameter, fällt aber direkt auf Tenant durch. Echte Layer folgen, sobald wir ihn brauchen.
- **Kein UI** für Settings-Bearbeitung — Settings werden in dieser Iteration per CLI / Seed gesetzt. UI kommt mit Admin View (§15, Welle 6).
- **Kein Schema-Validierungs-Framework** pro Key — wir akzeptieren JSON-Werte ohne Vorab-Validierung. Validierung kommt, wenn die Tabelle nicht mehr "5 Keys" hat.
- **Kein Audit-Log spezifisch für Settings** — Change-Log (Plan 04) wird das ohnehin automatisch abdecken, sobald `Setting` `BaseMixin` erbt.

## Datenmodell

### Eine Tabelle, zwei DBs

- `admin_db.setting` — nur `scope="platform"`-Einträge.
- `tenant_db.setting` — `scope ∈ {"tenant", "entity_type", "entity", "chat"}`.

Selbe Spaltenstruktur, zwei verschiedene Bases. Begründung: Plattform-Settings sind tenant-unabhängig und gehören zur Plattform-Steuerung; alle anderen sind tenant-lokal.

### Spalten

```python
scope:       str       # "platform" | "tenant" | "entity_type" | "entity" | "chat"
scope_ref:   str       # "" für platform; tenant-slug; entity-alias (bei entity_type); chat_id-String (bei chat)
entity_cls:  str       # nur bei scope="entity" gesetzt — Entity-Alias z.B. "core.task"
entity_id:   int       # nur bei scope="entity" gesetzt — ID der Zielentität, sonst 0
key:         str       # z.B. "ai.changes.mode"
value:       jsonb     # beliebig
set_by:      int       # User-ID, 0 bei System
# plus BaseMixin (id, created_at, updated_at, is_deleted)
```

Unique-Constraint `(scope, scope_ref, entity_cls, entity_id, key)` — ein Setting pro Schicht-Position. Bei nicht-entity Scopes sind `entity_cls=""` und `entity_id=0`.

Begründung für zwei getrennte Spalten (Entscheidung): typsicher (kein String-Parsen `"<alias>:<id>"` zur Laufzeit), Index nutzbar für Queries wie "alle Settings auf Task #45". Kosten: eine Spalte mehr, Unique-Index hat fünf Felder — vertretbar.

### Migrations

- `alembic/admin/versions/20260620_0002_setting.py` — `setting`-Tabelle in admin_db.
- `alembic/tenant/versions/20260620_0008_setting.py` — `setting`-Tabelle in tenant_db (Nummer ggf. nach Plan 01 anpassen).

## Code-Touchpoints

### `lib/entities/admin/setting.py` (neu)

```python
@register_entity("admin.setting")
class Setting(BaseMixin, AdminBase):
    __tablename__ = "setting"
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    entity_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    set_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

### `lib/entities/tenant/setting.py` (neu)

Identisch, aber gegen `TenantBase`, Alias `core.setting`.

### `lib/settings.py` (neu) — Resolver

```python
PLATFORM_DEFAULTS: dict[str, Any] = {
    "ai.changes.mode": "direct",                  # alternativ: "draft" | "draft_for_critical_fields"
    "agent.sub_chat.max_depth": 5,
    "agent.model.default": "gpt-5.5",
    "audit.change_log.retention_days": 365,
}

def resolve(key: str, *, tenant: str | None = None,
            entity_cls: str | None = None, entity_id: int | None = None,
            chat_id: int | None = None) -> Any:
    """Sucht Chat → Entity → Entity-Type → Tenant → Plattform → Default."""
```

Reihenfolge der Suche:
1. `chat_id` gesetzt? → `tenant_db.setting WHERE scope="chat" AND scope_ref=str(chat_id) AND key=?`
2. `entity_cls + entity_id` gesetzt? → `scope="entity" AND entity_cls=? AND entity_id=? AND key=?`
3. `entity_cls` gesetzt? → `scope="entity_type" AND scope_ref=<cls> AND key=?`
4. `tenant` gesetzt? → `scope="tenant" AND scope_ref=<tenant> AND key=?`
5. `admin_db.setting WHERE scope="platform" AND key=?`
6. `PLATFORM_DEFAULTS[key]` (KeyError, wenn nicht da → klarer Programmierfehler).

Caching: Resolver hält einen Per-Request-Cache (`ContextVar[dict]`) — denselben Key zweimal in einer Runde lesen kostet keinen Round-Trip.

### Setter

```python
def set_value(key: str, value: Any, *, scope: str,
              scope_ref: str = "", entity_cls: str = "", entity_id: int = 0,
              set_by: int = 0) -> None:
    """Upsert: Setting für (scope, scope_ref, entity_cls, entity_id, key) auf value."""
```

Validierung: `scope` muss aus den fünf zulässigen Strings sein; bei `scope="entity"` müssen `entity_cls` und `entity_id` gesetzt sein; `value` muss JSON-serialisierbar.

### Erster konkreter Use-Case

Für diese Iteration nehmen wir **`agent.model.default`** als ersten Use-Case — der Manager-Agent (`agents/manager/agent.py`) liest aktuell hardcoded ein Modell. Ersetzen durch:

```python
from lib.settings import resolve
model = resolve("agent.model.default", tenant=require_tenant())
```

Sichtbarer Effekt: Plattform-Admin kann das Default-Modell für die ganze Plattform setzen, ein Tenant kann es überschreiben. Demo-tauglich.

`ai.changes.mode` wird in Plan 04 (Change-Log) der zweite konkrete Use-Case, sobald AI-Änderungen tatsächlich angeschrieben werden.

## UI-Punkte

Keine in dieser Iteration. Settings werden per Seed-Skript oder kleinem CLI gesetzt:

```bash
python -m lib.settings_cli set --scope tenant --tenant demo \
    --key agent.model.default --value '"gpt-5.4"'
```

## Tests

- Resolver fällt sauber von Chat → Tenant → Platform → Default durch.
- Bei fehlendem Key in `PLATFORM_DEFAULTS`: `KeyError`.
- `set_value` mit ungültigem scope → ValueError.
- Cache reset zwischen Requests.

## Offene Fragen

- **Platform-Defaults: hardcoded in `lib/settings.py` oder in DB-Seed?** → entschieden: **hardcoded als Fallback** in `PLATFORM_DEFAULTS`. DB darf via `scope="platform"` überschreiben. Vorteil: Plattform läuft auch ohne migrierte `setting`-Tabelle; `KeyError` nur bei echten Programmierfehlern (Key nirgends definiert).
- **Welcher Setting-Key wird als Demo eingebaut?** → entschieden: **`agent.model.default`**. Manager-Agent liest das Modell künftig über `resolve(...)`, Tenant kann es überschreiben. Sofort sichtbarer Effekt. `ai.changes.mode` folgt mit Plan 04.
- **`scope_ref` für Entity — eine Spalte vs. zwei getrennte Spalten?** → entschieden: **zwei Spalten `entity_cls` + `entity_id`**. Typsicher, indexierbar, kein String-Parsen zur Laufzeit. Unique-Index ist `(scope, scope_ref, entity_cls, entity_id, key)`. Datenmodell oben angepasst.
- **Settings-Vererbung über Entity-Nesting** — wenn ein Vorgang in einem Projekt liegt und das Projekt eine Setting hat, soll der Vorgang sie erben? → entschieden: **in V1 nein**, Resolver nimmt nur den direkten Entity-Eintrag. Erweitern, wenn der Use-Case auftaucht.

## Aufwand

- Migrationen (2 DBs): 20 min
- Entity-Klassen: 15 min
- Resolver + Setter: 1h
- Cache: 20 min
- Use-Case-Einbau (`agent.model.default`): 30 min
- CLI: 30 min
- Tests: 45 min

**Gesamt: ~3.5h.**

## Abhängigkeiten

- Keine harte. Hilfreich, vorher Plan 01 (Trace-Context), weil `set_by` aus dem aktuellen User-Context kommt.

## Umgesetzt am 2026-06-20

- Migrationen: `admin_0002` (`alembic/admin/versions/20260620_0002_setting.py`) und `tenant_0009` (`alembic/tenant/versions/20260620_0009_setting.py`) — Plan sprach von tenant_0008, die Nummer war aber durch den AiChat-Anker-Plan belegt.
- Entities: `lib/entities/admin/setting.py` (Alias nicht polymorph — admin) und `lib/entities/tenant/setting.py` (Alias `core.setting`). Beide tragen `__change_log__ = False`.
- Resolver: `lib/settings.py` — sechs-stufiger Lookup (Chat → Entity → EntityType → Tenant → Platform-DB → `PLATFORM_DEFAULTS`), Per-Request-Cache via `ContextVar`, `KeyError` bei nirgends-definiertem Key.
- Setter: `set_value(...)` mit JSON-Serialisierbarkeitsprüfung, Upsert auf Admin- oder Tenant-DB, Cache-Invalidierung nach Schreibvorgang, Mini-Audit-Hook über `lib.audit.write_setting_change_log` (lazy import — funktioniert auch ohne Plan 04).
- CLI: `python -m lib.settings_cli {set|get|list}` — JSON-Value-Argument, sinnvolle Defaults für `scope_ref` (z.B. `--tenant demo` → `scope_ref="demo"` bei `scope=tenant`).
- Use-Case: `agents/manager/provider.py::get_tier2_model()` läuft jetzt über `resolve("agent.model.default", tenant=...)` mit Env-Fallback (`TIER_2_MODEL`).
- Cache-Reset: Gateway-Middleware `_settings_cache_per_request` in `gateway/main.py` (vor allen Routen).
