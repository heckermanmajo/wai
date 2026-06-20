# Plan 04 — Change-Log (Entity-Audit-Trail)

**Welle 1, Feature 4. Vision-Refs: §26, §27 (Settings-Use-Case).**

## Ziel

Automatischer Audit-Trail für jede Feld-Änderung an jeder `BaseMixin`-Entität. Append-only in `logging_db.entity_change`. Pro logischem Save **ein** Eintrag mit `field_diffs` als JSONB-Liste. Verlaufs-Tab pro Entity-Overlay.

Damit ist nach Plan 04 jede Änderung im System nachvollziehbar:
- "User 12 hat am 2026-06-21 14:33 Task #45 von 'offen' auf 'erledigt' geschoben — Trace abc-123 → das war im Chat #88."

## Schnittweise — was NICHT reinkommt

- **Kein Auto-Generator** "Status-Update → fachliches Event in Vorgangs-Timeline". Das ist eine Erweiterung, kommt mit Welle 3 (Events am Vorgang).
- **Kein Draft/Confirm-Modus** für AI-Änderungen. Setting `ai.changes.mode` wird zwar gelesen und in `field_diffs.meta` gespeichert, aber der Draft-Workflow selbst kommt mit Plan 12 (Aktionen-Scopes).
- **Kein Bulk-Modus** (ein Eintrag pro Bulk-Operation). V1: pro Row ein Eintrag.
- **Kein Semantic-Index** auf `summary`. Querschnitts-Thema, kommt später.
- **Keine Retention-Job** der alte Einträge wegputzt. Setting existiert, Job folgt.

## Datenmodell

### `logging_db.entity_change`

```python
tenant_id:    str       # Eingrenzung pro Tenant
target_cls:   str       # "core.task", "core.project", ...
target_id:    int       # ID der geänderten Entität
change_type:  str       # "create" | "update" | "delete" | "soft_delete"
actor_type:   str       # "human" | "ai" | "system"
actor_id:     int       # User-ID oder Agent-ID, 0 bei system
agent_name:   str       # leer bei human/system
trace_uid:    str       # leer bei deterministischen Calls ohne Chat-Kontext
field_diffs:  jsonb     # Liste [{field, old, new}], leer bei create/delete
summary:      str       # kurzer Satz, AI- oder default-generiert
# plus BaseMixin (created_at als Audit-Timestamp)
```

Indexe:
- `(tenant_id, target_cls, target_id, created_at DESC)` — Default-Read-Pattern für Verlaufs-Tab.
- `(trace_uid)` — Sprung von Trace-Achse zu allen Changes dieses Runs.
- `(actor_type, created_at DESC)` — globaler Filter "alle AI-Änderungen letzte Woche".

### Migration

`alembic/logging/versions/20260620_0003_entity_change.py`. Standard-`_base_columns()` + die 9 fachlichen Spalten.

## Code-Touchpoints

### `lib/entities/logging/entity_change.py` (neu)

Klassische Entity-Klasse, kein `register_entity` (Logging-Tabellen sind nicht polymorph adressierbar von außen).

### `lib/audit.py` (neu) — Hooks und Buffer

```python
def install_change_log_hooks() -> None:
    """Registriert SQLAlchemy-Event-Listener auf TenantBase + AdminBase."""
```

Mechanik:
- `before_flush`-Hook am `Session`: inspiziert `session.new`, `session.dirty`, `session.deleted`.
- Pro betroffene Row baut er ein `pending_change`-Dict im Session-State (nicht in DB!).
- `after_flush`-Hook: liest die `pending_change`-Liste und schreibt sie in `logging_db.entity_change` (separate Session). Damit landen Audit-Einträge **erst nach erfolgreichem Commit** der eigentlichen Änderung.

**Ein Eintrag pro logischem Vorgang**: alle Rows, die in einem Session-Flush gleichzeitig dirty sind, werden **nicht** zusammengelegt — pro Row gibt es ein `EntityChange`. Aber: die Feld-Diffs *innerhalb* einer Row landen als Liste in *einem* Eintrag, nicht als mehrere Einträge.

### Actor + Trace aus ContextVar

Aus Plan 01:
```python
from lib.tenant_context import get_actor, get_trace_uid
actor_type, agent_name = get_actor()
trace_uid = get_trace_uid() or ""
```

### Soft-Delete-Sonderfall

`BaseMixin` hat `is_deleted`. Wenn dieses Feld von `False` auf `True` springt, ist das ein `soft_delete`, nicht ein normales `update`. Hook erkennt das und setzt `change_type` entsprechend.

### Opt-Out pro Entity-Typ

Eine Klasse kann ein Klassenattribut `__change_log__ = False` setzen, um aus der Erfassung rauszufallen. Wichtig für:
- `SemanticSnippet` (schreibintensiv, kein Audit-Wert).
- `AiMessage`, `AiToolCall` (gehören zur Telemetrie, nicht zur Fachlichkeit).
- `Setting` selbst — Opt-Out, mit eigenem **Mini-Audit** (siehe nächster Abschnitt). Vermeidet die Henne-Ei-Schleife (Hook ruft `resolve()` auf, das wieder einen Hook auslöst, …).

### Feld-Diff-Truncation für große Texte

Felder wie `Document.body` können mehrere kB groß sein. Volltext im Audit würde `logging_db` schnell aufblähen. Regel:

- Pro Feld-Diff: harte Grenze **4 kB pro Wert** (alt und neu jeweils).
- Bei Überschreitung: statt `{"field": "body", "old": "<12kB Text>", "new": "<14kB Text>"}` wird `{"field": "body", "old": null, "new": null, "truncated": true, "old_len": 12345, "new_len": 14567}` gespeichert.
- UI im Verlaufs-Tab zeigt bei `truncated: true` nur "Inhalt geändert (12 kB → 14 kB)" statt Diff-Markup.

Konstante `CHANGE_LOG_FIELD_MAX_BYTES = 4096` in `lib/audit.py`.

### Mini-Audit für Settings

`Setting` hat `__change_log__ = False`. Statt vom Generic-Hook erfasst zu werden, schreibt `lib/settings.set_value` direkt einen Audit-Eintrag:

```python
def set_value(key, value, *, scope, scope_ref="", entity_cls="", entity_id=0, set_by=0):
    old = _get_raw(scope, scope_ref, entity_cls, entity_id, key)  # None bei create
    _upsert(...)
    _write_setting_change(
        scope=scope, scope_ref=scope_ref, entity_cls=entity_cls, entity_id=entity_id,
        key=key, old=old, new=value, set_by=set_by,
    )
```

`_write_setting_change` schreibt nach `logging_db.entity_change` mit `target_cls="admin.setting"` (oder `core.setting`), `target_id=setting.id`, `change_type="update"|"create"`, `field_diffs=[{"field": "value", "old": old, "new": new}]`. Damit ist Setting-Audit-Spur kompatibel zum Verlaufs-Tab, ohne den ORM-Hook zu durchlaufen.

### Strikte Feld-Gleichheit

Eine Feld-Änderung liegt vor, wenn der Datenbankwert sich strikt unterscheidet (`old != new`). Keine semantische Normalisierung (`""` ist nicht `None`, `"0"` ist nicht `0`). Begründung: vorhersagbar, kein Edge-Case-Sumpf, echte DB-Speicherungs-Unterschiede werden nicht versteckt.

### Summary-Generierung

In V1 deterministisch ohne LLM:
- `create`: `"Erstellt"` plus optional Titel.
- `delete`/`soft_delete`: `"Gelöscht"`.
- `update`: `"3 Felder geändert: status, priority, due_at"`.

Bei AI-Änderungen darf der Agent vor dem Save den `summary` explizit setzen über `set_change_summary("Beschreibung um Reklamationsdetails ergänzt")` in `lib/audit.py`. Hook liest diesen ContextVar, falls gesetzt, statt der Default-Vorlage.

## UI-Punkte

### Verlaufs-Tab im Entity-Overlay

Das `EntityOverlay`-Component bekommt einen neuen Tab "Verlauf":

```
| Detail | Notizen | Kommentare | Anhänge | Verlauf |
```

Verlaufs-Tab listet:
- Zeile pro Eintrag: `[YYYY-MM-DD HH:mm]  [Icon: human/ai/system]  Actor-Name  —  Summary`
- Aufklappen zeigt `field_diffs` als Tabelle (Feld | Vorher | Nachher), bei Text-Feldern mit Diff-Markup.
- Bei AI-Einträgen mit `trace_uid`: Mini-Link "→ Trace anzeigen" (öffnet Debug-View, sobald Plan 06 da ist).

Gateway-Endpoint: `GET /api/entity/{alias}/{id}/changes?limit=50&offset=0`.

## Tests

- Update an einem `Task`-Feld → genau 1 Eintrag in `entity_change`, korrekte `field_diffs`.
- Update an 3 Feldern in 1 Save → 1 Eintrag mit 3 Diffs.
- Update an 2 Tasks im selben Commit → 2 Einträge, je 1 pro Row.
- AI-Änderung mit gesetztem `set_change_summary` → Summary übernommen.
- `SemanticSnippet`-Update → kein Eintrag (Opt-Out greift).
- Migration up/down.

## Offene Fragen

- **Wie tief field_diffs bei Text?** → entschieden: **4 kB pro Wert**, darüber Truncation auf `{truncated: true, old_len, new_len}`. Implementiert in `lib/audit.py` via `CHANGE_LOG_FIELD_MAX_BYTES = 4096`. UI zeigt nur "Inhalt geändert (12 kB → 14 kB)".
- **Was zählt als 'Feld-Änderung'?** → entschieden: **strikte DB-Gleichheit** (`old != new`). Keine Normalisierung von `""` ↔ `None` o.Ä. — vorhersagbar, keine Edge-Cases.
- **Was passiert bei Migration-induzierten Änderungen?** → kein Problem: Alembic macht raw SQL, ORM-Hook läuft nicht. Dokumentieren in der Plan-Notiz "wie der Hook funktioniert" (siehe Abschnitt "Nicht-ORM-Pfade" unten).
- **`Setting` selbst auditen oder nicht?** → entschieden: **Setting opt-out** (`__change_log__ = False`) + eigener **Mini-Audit** in `lib/settings.set_value` (siehe oben). Schreibt direkt nach `logging_db.entity_change` mit `target_cls="admin.setting"`. Vermeidet Henne-Ei-Schleife.
- **Nicht-ORM-Pfade** — wenn jemand raw SQL macht (Bulk-Update), läuft der Hook nicht. → entschieden: **ORM-only, dokumentieren**. In `CLAUDE.md` und in `lib/audit.py`-Doctring eine Notiz: "Bulk-Updates per raw SQL umgehen den Change-Log. Wenn Audit-Coverage wichtig ist, ORM-Loop verwenden oder den Audit-Eintrag manuell schreiben." Kein DB-Trigger in V1.

## Aufwand

- Migration + Entity: 20 min
- Hook-Mechanik (before_flush / after_flush): 2h
- Actor/Trace-Integration via ContextVar: 30 min
- Summary-Generator + Override-Var: 30 min
- Opt-Out-Mechanik + Anwendung auf bekannte Tabellen: 20 min
- Truncation-Logik für große Text-Diffs: 20 min
- Setting-Mini-Audit in `lib/settings.set_value`: 30 min
- Verlaufs-Tab-API + UI: 2h
- Tests: 1.5h

**Gesamt: ~7.5h. Größtes Feature in Welle 1.**

## Abhängigkeiten

- **Plan 01** (Trace-Context, Actor-Context) — harte Abhängigkeit, sonst weiß der Hook nicht, wer schreibt.
- **Plan 03** (Settings) — weich, für die `ai.changes.mode`-Logik. Ohne Plan 03 fällt das aus, der Change-Log läuft trotzdem.

## Umgesetzt am 2026-06-20

- Entity: `lib/entities/logging/entity_change.py` (`EntityChange`-Klasse mit `__change_log__ = False`), Migration `logging_0003` (`alembic/logging/versions/20260620_0003_entity_change.py`) inkl. der drei Indexe aus dem Plan.
- Hook-Mechanik: `lib/audit.py` mit `install_change_log_hooks()` — `before_flush` sammelt Diffs aus `session.dirty`/`session.deleted`, `after_flush` adressiert frische IDs aus `session.new` (kein `field_diffs` bei `create`, wie Plan 04 will), `after_commit` drained die Outbox in einer separaten Logging-Session; `after_rollback` löscht die Outbox.
- Actor/Trace: Hook zieht Werte aus `lib/tenant_context` (`get_actor`, `get_user`, `get_trace_uid`, `get_tenant`).
- Soft-Delete-Sonderfall: `is_deleted` von `False` → `True` ergibt `change_type="soft_delete"`.
- Opt-Out gesetzt für: `SemanticSnippet`, `AiMessage`, `AiToolCall`, `Setting` (admin+tenant), `EntityChange`, `Event`, `Trace`, `ErrorReport` — alle via `__change_log__ = False`.
- Truncation: `CHANGE_LOG_FIELD_MAX_BYTES = 4096`, oberhalb wird `{truncated: true, old_len, new_len}` geschrieben.
- Setting-Mini-Audit: `lib/audit.write_setting_change_log(...)` wird von `lib/settings.set_value(...)` lazy aufgerufen. Plattform-Setting → `target_cls="admin.setting"`, Tenant-Setting → `target_cls="core.setting"`. Setting-Diff trägt Schicht-Info (`scope`, `scope_ref`, `key`) zusätzlich.
- Summary-Generator: deterministische Defaults (Erstellt/Geloescht/`N Feld(er) geaendert: …`), per `set_change_summary("…")` override-bar (ContextVar, einmalig).
- Gateway-Endpoint: `GET /{slug}/entity/{cls}/{id}/changes?limit=&offset=` (auth-geschützt via `require_user`), liefert `{changes, limit, offset, count}`.
- UI: Tabs am `EntityOverlay` (Detail/Verlauf), neuer Verlaufs-Tab in `interface/components/overlays/EntityChangesTab.tsx` mit Aufklappen pro Eintrag (Feld-Diff-Tabelle, Trace-Link). API-Wrapper `interface/lib/api/changes.ts`.
- Hook-Install: einmalig in `gateway/main.py` direkt nach Import (idempotent).
