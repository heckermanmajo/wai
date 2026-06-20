# WAI — Arbeitsanweisungen für Claude in diesem Repo

## Quellen der Wahrheit
- **`VISION.md`** — die End-Stufe der Plattform, lebendiges Dokument. Beim Start einer neuen Session immer kurz die "Geklärte Punkte"-Sektionen und offene Diskussionspunkte überfliegen, damit der Stand der Konzept-Diskussion klar ist.
- **`docs/plans/`** — pro Vision-Feature ein Implementierungsplan (kleinteilig, iteriert). Format siehe unten.

## Iterations-Prozess

Wir arbeiten die Vision in Wellen ab, eine Welle = ein Bündel zusammengehöriger Features. Pro Feature ein **Plan-File** unter `docs/plans/NN-feature-name.md`. Der Lebenszyklus eines Features ist immer derselbe:

1. **Planen** — Plan-File schreiben (oder existierenden öffnen). Feste Struktur:
   - **Ziel** (1–2 Sätze)
   - **Schnittweise** — was bewusst NICHT in diese Iteration kommt
   - **Datenmodell** — Tabellen, Felder, Migrations
   - **Code-Touchpoints** — welche Files/Module
   - **UI-Punkte** — welche Overlays/Pages
   - **Tests** — Mindest-Cases
   - **Offene Fragen** — was vor Code geklärt werden muss
   - **Aufwand** — grobe Schätzung pro Block
   - **Abhängigkeiten** — auf welche anderen Pläne hart/weich
2. **Durchsprechen** — Plan-File mit dem User Punkt für Punkt durchgehen. Offene Fragen entscheiden. Plan-File wird beim Durchsprechen mit den Antworten ergänzt (die "Offene Fragen"-Sektion bleibt, mit "→ entschieden: …" pro Punkt).
3. **Umsetzen** — Plan abarbeiten. Bei Abweichungen vom Plan zurück zur Diskussion, **nicht** stillschweigend deviieren. Wenn neue Erkenntnisse auftauchen, Plan-File updaten — der Plan ist die Wahrheit, nicht der Chat-Verlauf.
4. **Plan abhaken** — am Ende des Plan-Files eine Sektion "**Umgesetzt am YYYY-MM-DD**" mit kurzem Hinweis, was tatsächlich rausgekommen ist (Commit-Hash, Migrations-Revisions, Notizen). Vision-Status der entsprechenden §-Sektion(en) aktualisieren (`fehlt` → `teilweise` / `vorhanden`).

## Aktueller Stand (Stand 2026-06-20)

- VISION.md ist auf Stand "Geklärte Punkte Runde 4" (siehe Dokument).
- Implementierungs-Reihenfolge: **6 Wellen**, geplant sind aktuell die ersten beiden:
  - **Welle 1 (Audit-Fundament):** Pläne 01–04
  - **Welle 2 (Debug-Sichtbarkeit):** Pläne 05–06
- Pläne 03–06 für die Wellen 3+ existieren noch nicht — bewusst, erst nach Erkenntnissen aus Welle 1+2 schreiben.
- Diskussionen zu den 6 Plänen stehen noch aus. Empfohlener Startpunkt: **Plan 01**, dann Plan 02 + 05 zusammen, dann Plan 03, dann Plan 04, dann Plan 06.

## Sub-Agents — wo es Sinn macht

Sub-Agents (über das `Agent`-Tool) sind beim Arbeiten in diesem Repo häufig der richtige Weg. Faustregeln:

**Pro `Explore`-Subagent:**
- Mehr als 3 Queries, um ein Symbol oder File zu finden? → `Explore` statt direkter `grep`.
- "Wo wird X überall verwendet?" über mehrere Module → `Explore` mit Breite "medium" oder "very thorough".
- Aufwärm-Phase einer Plan-Diskussion ("zeig mir den aktuellen Stand von X im Code, bevor wir Plan Y besprechen") → `Explore`.

**Pro `Plan`-Subagent:**
- Wenn ein Plan-File entstehen oder substanziell überarbeitet werden soll und der Kontext-Stand im Code unklar ist → `Plan`-Agent erst.
- Für Architektur-Trade-offs bei komplexen Features, bevor das Plan-File geschrieben wird.

**Pro `general-purpose`-Subagent:**
- Größere parallele Recherchen, deren Ergebnisse den Hauptkontext sonst zumüllen würden.
- "Schau dir alle MCP-Server an und schreib mir, wo überall `kind`-Field gut reinpasst" — solche Multi-File-Aufträge.

**Workflows (`Workflow`-Tool):**
- Nur, wenn der User explizit "workflow" sagt oder ein /code-review etc. anfordert. Nicht eigenmächtig starten — die kosten viele Tokens.

**Wichtig:** Beim Umsetzen eines Plans nicht den ganzen Plan an einen `general-purpose`-Subagent rauswerfen. Der Plan wird **im Haupt-Loop** umgesetzt, weil dort die Diskussionsentscheidungen und das Vision-Verständnis sitzen. Sub-Agents sind für **Recherche, Suche, isolierte Mini-Refactors** — nicht für "implementier mir bitte Plan 04".

## Stil-Konventionen

- Deutsch in der Konversation, deutsche Kommentare im Code (Stand jetzt — bei Mehrsprachen-Switch hier ergänzen).
- UTF-8-Umlaute überall, nie ä→ae etc. (siehe `~/.claude/CLAUDE.md`).
- Keine FKs zwischen Tabellen — Konvention im Repo, siehe `lib/mixins.py`.
- Polymorphes Verlinken über `target_cls` (String-Alias aus `@register_entity`) + `target_id`.
- Drei DBs: `admin_db`, `logging_db`, `tenant_<slug>`. Tabellen-Zuordnung über die jeweilige `Base`-Klasse (`AdminBase` / `LoggingBase` / `TenantBase`).
- Alembic pro DB-Branch eigene Versions-Reihe (`alembic/admin/versions/`, `alembic/logging/versions/`, `alembic/tenant/versions/`).
- Sync-SQLAlchemy, kein async-DB. In async-Code via `asyncio.to_thread` einwickeln.
- Telemetrie: `EventEmitter` (`lib/events.py`), Events landen in `logging_db.event` (außer `VOLATILE_EVENT_TYPES`).

## Anti-Patterns

- **Nicht** Plan überspringen und gleich code-en, auch wenn das Feature klein wirkt — der Diskussions-Schritt fängt Vision-Inkonsistenzen ab.
- **Nicht** mehrere Pläne in einem Commit umsetzen. Ein Plan = ein in sich abgeschlossener Commit-Cluster.
- **Nicht** Vision-Sektionen umnummerieren, wenn neue eingefügt werden — am Ende anhängen, sonst zerfallen Referenzen in Plan-Files.
- **Nicht** Sub-Agents mit dem ganzen Repo-Kontext überfluten — präzise Aufträge, Plan-File-Pfade als Anker mitgeben.

## Quick-Start für neue Session

1. `VISION.md` — Abschnitte "Geklärte Punkte Runde N" lesen.
2. `docs/plans/` — durchgehen, prüfen welche Plans "Umgesetzt am …" tragen und welche offen sind.
3. Mit dem User klären: welcher Plan ist jetzt dran (planen / durchsprechen / umsetzen)?
4. Bei Recherche-Bedarf → `Explore`-Subagent, **nicht** seriell selbst grepen.
