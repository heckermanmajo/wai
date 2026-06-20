# WAI — Endvision

> Lebendiges Dokument. Sammelt die großen Konzepte für die Endstufe der Plattform.
> Aus diesem Dokument ziehen wir später konkrete Features und bauen sie inkrementell ein.
>
> Status-Legende pro Konzept:
> - **vorhanden** — schon implementiert
> - **teilweise** — Grundbausteine da, aber unvollständig
> - **fehlt** — noch gar nicht angelegt

---

## Leitidee

Die Plattform ist ein **AI-natives Arbeitssystem**: minimalistische UI, der Großteil der Interaktion läuft über Chat. Die Datenmodelle sind bewusst generisch ("Vorgang", "Aufgabe", "Notiz", "Memory") — die fachliche Spezifik kommt nicht aus festen Entitäten, sondern aus **freitextlichen Beschreibungen** plus **nutzerdefinierten Workflows**, die die AI verwendet, um konkrete Geschäftsprozesse abzubilden. Klassische Funktionen (Task abhaken, Dokument versionieren) bleiben deterministisch erhalten; alles Darüberhinausgehende läuft über AI plus Aktionen.

---

## 1. Projekte und Vorgänge — die zwei Arbeits-Klammern

**Status:** Projekt teilweise (es gibt `Project` in `lib/entities/tenant/project.py`). Vorgang als V1 vorhanden (`Process` in `lib/entities/tenant/process.py`, MCP `process_mcp`, Plan 07 umgesetzt 2026-06-20). Fachliche Events am Vorgang als V1 vorhanden (`BusinessEvent` + `events_mcp`, Plan 08 umgesetzt 2026-06-20, siehe §2). Fehlt für die End-Stufe noch: Milestones (§5), Workflow-Bindung (§7), Listing/Timeline-UI (mit Explorer §18 / Visualisierung §11).

### Entscheidung: Projekt und Vorgang werden semantisch getrennt

Auch wenn beides technisch ähnlich aussieht (nestbar, mit Notizen/Tasks/Events behangen, mit Freitext-Beschreibung), trennen wir die beiden Begriffe **wegen der semantischen Klarheit für den Nutzer**.

- **Projekt** = die **größere Klammer**, oft langfristig, oft intern getrieben.
  Beispiel: "Wir entwickeln ein neues Produkt und bringen es auf den Markt."
  Ein Projekt kann mehrere Vorgänge enthalten — z.B. eine TÜV-Abnahme, einzelne Kundenfälle, interne Vorbereitungs-Schritte.

- **Vorgang** = die **kleinere Arbeitseinheit**, oft anlassgetrieben, oft extern getriggert.
  Beispiel: "Ein Kunde meldet sich und will X." / "Reklamation Nr. 4711." / "TÜV-Abnahme für Produkt Y."
  Ein Vorgang kann (muss aber nicht) zu einem Projekt gehören.

### Gemeinsame Eigenschaften (beide)
- **Nestbar**: Projekte können Unter-Projekte, Vorgänge können Unter-Vorgänge haben.
- **Polymorph anhängbar**: Notizen, Dokumente, Tasks, Milestones, Nutzer, Events, Memory, Adressen, Orte hängen an beidem.
- **Beschreibung first**: Freitext ist der Hauptträger der fachlichen Bedeutung.
- **Typ-Tag** (optional): Beide können einen Typ tragen, der auf einen Workflow zeigt.

### Beziehung
- Ein **Vorgang kann zu einem Projekt gehören** (optionale `project_id`).
- Ein Projekt zeigt seine zugehörigen Vorgänge in der Timeline.

### Was zu klären ist
- Brauchen wir noch eine dritte Ebene über Projekt (Programm/Portfolio)? — vermutlich nein, das geht über Projekt-Nesting.
- ~~`Project` bleibt der bestehende Code-Name; `Vorgang` wird als neue Entität `Process` (oder `Case`?) angelegt — Code-Name müssen wir noch festlegen.~~ → entschieden mit Plan 07: Class-Name `Process`, Alias `core.process`.

---

## 2. Events auf Vorgängen

**Status:** V1 vorhanden — `BusinessEvent` in `lib/entities/tenant/business_event.py` (Tabelle `event`, Alias `core.event`), MCP `events_mcp` (Port 8506), Helper `lib/business_events.py`, Auto-Erzeuger `lib/audit_to_event.py` (Whitelist über Settings, Default `status_changed` aus Process-Status-Wechsel), Plan 08 umgesetzt 2026-06-20. Fehlt für die End-Stufe: Timeline-UI am EntityOverlay (eigener Plan), erweiterbare Auto-Rules per UI/Setting, Workflow-Reaktionen (§7), Mail-/Kalender-Ingest (§20), Visualisierungen (§11).

### Vision
- **Fachliche Events** als eigene Entität in der Tenant-DB: "Anruf am 12.6.", "Mail rausgegangen", "Termin", "Statuswechsel".
- Jedes Event hat: Zeit, Typ, Beschreibung, Auslöser (User oder AI), polymorphe Verankerung an Vorgang/Entität.
- Events sind die **Timeline-Quelle** für die Detailansicht eines Vorgangs.
- Sowohl manuell erfassbar als auch automatisch erzeugt (z.B. durch Aktionen, durch Workflow-Schritte).

### Brücke zur Telemetrie: `trace_uid`
Jedes fachliche Event trägt ein optionales `trace_uid`-Feld, das auf den Telemetrie-Trace (`logging_db.trace`) zeigt, in dem das Event entstanden ist. Damit existiert die Verknüpfung **Fachlichkeit ↔ Chat-Runde**:

- "Event 'Status auf wartet-auf-Kunde gewechselt' am Vorgang 4711 → trace_uid abc-123 → Chat #87 / Tool-Call `update_status` mit den exakten Argumenten."
- Vom Vorgangs-Timeline-Eintrag in zwei Klicks im Debug-View (§16) beim auslösenden LLM-Prompt landen.
- Bei rein menschlichen Events (manuell erfasst, kein AI-Run) bleibt `trace_uid` leer.

### Abgrenzung
- **Logging-Events** (`logging_db.event`): technische Telemetrie pro Chat-Runde, nicht fachlich relevant.
- **Vorgangs-Events** (`tenant_db.event`): fachlich relevant, durchsuchbar, semantisch indexierbar.
- **Change-Log** (`logging_db.entity_change`, §26): Feld-Diffs auf einer Entität — die Buchhaltung, nicht die Timeline. Ein fachliches Event kann aus einem Change-Log-Eintrag entstehen (z.B. `status`-Feld geändert → automatisches "Statuswechsel"-Event), die beiden bleiben aber getrennt: Change-Log ist universell pro Feld, Event ist kuratiert pro Bedeutung.

---

## 3. Notizen, Dokumente, Anhänge, Kommentare

**Status:** vorhanden — `Note`, `Document`, `DocumentVersion`, `Attachment`, `Comment` existieren bereits, alle polymorph anhängbar.

### Vision
- Alles bleibt polymorph: jede Entität kann Notizen/Dokumente/Anhänge/Kommentare tragen.
- Dokumente sind **versionsbasiert** (gibt es) — Diff-Ansicht im UI ist Teil davon (gibt es als Overlay).
- AI kann Dokumente erzeugen, ändern, zusammenfassen, übersetzen — über Aktionen (siehe §13).
- **Browse/Suche/Listen-UX** über diese Entitäten lebt nicht hier, sondern im **Explorer** (§18). Diese Sektion beschreibt nur die Entitäten selbst.

### Was noch dünn ist
- Konsistente UX für "Dokument an Vorgang anhängen" über den Chat (Action-Flow).
- Klare Trennung "Note" vs. "Comment" vs. "Memory" in der UI dokumentieren (siehe §6).

---

## 4. Aufgaben (Tasks)

**Status:** vorhanden — `Task` (`lib/entities/tenant/task.py`) mit Status/Priorität/due_at/assignee, polymorph anhängbar.

### Vision
- Bleibt als **allgemeiner Aufgabentyp** — keine spezialisierten Task-Untertypen.
- Determministisch abhakbar (klassisches Häkchen) — kein AI-Workaround nötig.
- Kann an Vorgang, Milestone, Dokument, User, ... hängen.
- AI kann Tasks erzeugen, zuweisen, abschließen — über Aktionen.

---

## 5. Milestones

**Status:** fehlt — keine Milestone-Entität.

### Vision
- Eigene Entität `Milestone` in der Tenant-DB.
- Felder: Name, Beschreibung, Zieltermin, Status (offen/erreicht/verfehlt), polymorphe Anhängung.
- **Verschachtelung**: Vorgang → Milestone → Tasks. Aber: Tasks können auch direkt am Vorgang hängen, ohne Milestone.
- Wird in der Vorgangs-Visualisierung als zeitliche Achse oder als Burndown gezeigt (siehe §12).

---

## 6. Memory — AI-Notes mit Scope

**Status:** fehlt — keine Memory-Entität.

### Vision
- **Memory** ist eine Notiz, die in jeden relevanten AI-Kontext mit eingespeist wird.
- **Scopes:**
  - **Tenant-weit (global)**: "Wir duzen Kunden." / "Antworte immer auf Deutsch."
  - **User-spezifisch**: "Mich darfst du duzen." / "Mich bitte siezen."
  - **Entity-spezifisch** (Projekt, Vorgang, Kunde, …): "Dieser Kunde hasst Telefonate." / "Reklamation läuft über Anwalt, vorsichtig formulieren."
- Memory ist **AI-orientiert**, anders als eine normale Notiz: sie wird automatisch in den Prompt-Kontext aufgenommen, sobald die AI mit dem zugehörigen Scope arbeitet.
- Memory ist **durchsuchbar** und semantisch indexiert.

### Reihenfolge im Prompt-Kontext
**Vom Großen ins Kleine: Tenant → User → Entity.**

Begründung: AI-Prompts funktionieren so, dass spätere/spezifischere Informationen die früheren überschreiben oder verfeinern. Tenant setzt den allgemeinen Ton ("Wir duzen Kunden"), User verfeinert ihn auf die handelnde Person ("Mich darfst du duzen"), Entity gibt den situativen Kontext ("Dieser eine Kunde will gesiezt werden"). Das Untere lebt im Kontext des Oberen.

Bei mehreren Entity-Memories (z.B. Vorgang in einem Projekt, beide haben Memory): **Projekt vor Vorgang** — also auch hier vom Größeren ins Kleinere.

### Abgrenzung
- **Note**: menschenorientierte Notiz, wird nur explizit gelesen.
- **Memory**: AI-Kontext-Notiz, fließt automatisch in Prompts ein.
- **Comment**: Diskussions-Eintrag, mehrere Autoren, eher chronologisch.

### Was zu klären ist
- Wie verhindern wir Memory-Sprawl? (Größenlimit pro Scope, Verfallsdatum, "stale"-Markierung?)
- Welche Scopes mischen sich, wenn ein User mit einem Kundenvorgang arbeitet? Reihenfolge / Priorität?

---

## 7. Nutzerdefinierte Workflows

**Status:** fehlt — kein Workflow-Konzept.

### Vision
- Ein **Workflow** ist eine Beschreibung eines Geschäftsprozesses, die die AI versteht und anwendet.
- **Kein** klassisches BPMN, **kein** Skill-Definition-Code. Eher: "So läuft bei uns ein Verkauf ab: Kunde meldet sich, wir legen einen Vorgang an, der hat eine Beschreibung, daraus entsteht ein Angebot, …"
- Workflows werden **vom Nutzer geschrieben** oder **mit AI-Hilfe erstellt** (Chat: "Lass uns unseren Reklamationsprozess aufschreiben").
- Workflows verweisen auf **generische Entitäten** (Projekt, Vorgang, Task, Milestone, Memory, …) und beschreiben deren Verwendung im Kontext.
- Workflows können **AI-Aktionen vorschlagen** (z.B. "Bei diesem Workflow gibt es nach Phase 2 die Aktion: Angebot generieren").

### Struktur: Freitext-Pflicht, Struktur-Optional

Workflows sind primär **Freitext** — ein Nutzer kann komplett rein erzählend einen Prozess beschreiben, und die AI nutzt das.

**Zusätzlich** kann ein Workflow optionale strukturierte Bestandteile haben, die bei Bedarf gepflegt werden:

- **Phasen** (optional): benannte Abschnitte des Prozesses (z.B. "Anfrage", "Angebot", "Abschluss"), jeweils mit eigenem Freitext.
- **Schritte innerhalb einer Phase** (optional): kleinere Etappen, die nacheinander oder parallel laufen.
- **Übergänge** (optional): Bedingungen, wann von einer Phase in die nächste gewechselt wird.
- **Tool-/Aktions-Referenzen** (optional): welche Tools oder Aktionen in einer Phase typischerweise genutzt werden.
- **Beteiligte Rollen** (optional): wer in welcher Phase verantwortlich ist.

**Warum optional?** Mehr Struktur gibt dem Nutzer höhere Kontinuität, Klarheit und Sicherheit — er sieht: "okay, jetzt passiert das, dann das, dann wird dieses Tool verwendet". Aber das soll nicht erzwungen werden, denn am Anfang reicht oft eine reine Prosa-Beschreibung, und die AI kann damit schon arbeiten. Struktur wird nachgereicht, wenn der Prozess sich verfestigt.

### Modellierung
- Eigene Entität `Workflow` mit Name, Beschreibung (Freitext, primär) und optionaler Struktur (Phasen, Schritte, Übergänge, Tool-Refs).
- Workflows können mit einem Projekt-/Vorgangs-Typ-Tag verknüpft werden, sodass die AI automatisch den passenden Workflow heranzieht.

### Was zu klären ist
- Wird ein Projekt/Vorgang einem Workflow **automatisch** (via AI bei Anlage) oder **explizit** (per Auswahl) zugeordnet? Wahrscheinlich beides erlaubt, Default automatisch.
- Wie versionieren wir Workflows, wenn sie sich ändern, während ein Vorgang noch läuft? — eingefrorene Workflow-Version pro Vorgang oder immer live?

---

## 8. Meta-MCPs / Worker-Rollen (virtuelles Büro)

**Status:** teilweise — es gibt 13 Fach-Agents (`agents/`) und ein Manager-Agent, der per Sub-Agent-Delegation arbeitet (aktuell hauptsächlich `sales_support`). Das Pattern ist da, aber noch nicht systematisch ausgebaut.

### Vision
- Das **virtuelle Büro**: Der Nutzer redet mit dem **Hauptmanager**. Der Manager delegiert an spezialisierte Worker.
- **Beispiele für Worker-Rollen:**
  - **Archivar** — sucht und legt Dokumente ab, findet alte Vorgänge wieder.
  - **Web-Researcher** — recherchiert online, sammelt Quellen.
  - **Visualizer** — generiert Bilder, SVGs, Diagramme.
  - **Diktat-Tippse** — wandelt Sprache in Text.
  - **Coach** — fragt aktiv beim Nutzer nach, schult.
  - **Finance**, **HR**, **Sales-Support**, **Law**, **Designer**, **Project-Manager**, **Automation-Builder**, **Scrum-Master**, **Improvement-Manager** — fachliche Sub-Agents.
- Der Manager **zerlegt** einen Nutzer-Auftrag in Unteraufgaben, ruft die zuständige Rolle, sammelt Ergebnisse, antwortet.
- Jede Rolle ist ein eigener **MCP-Server** mit eigenen Tools.

### Sub-Agent-Lifecycle-Events
Damit die UI in Echtzeit zeigen kann, **welche Rolle gerade arbeitet**, emittiert der Manager (und jeder Sub-Agent rekursiv) standardisierte Lifecycle-Events in den EventEmitter-Stream:

- `sub_agent_started` — `{role, parent_trace_uid, sub_trace_uid, sub_chat_id, task_brief}`
- `sub_agent_progress` — `{role, sub_trace_uid, status_text}` (optional, vom Sub-Agent selbst gepostet: "Archivar: durchsuche letzte 30 Tage …")
- `sub_agent_completed` — `{role, sub_trace_uid, summary, outcome_preview, duration_ms, status}` (entspricht dem Result-Contract aus §10)

Diese Events tauchen sowohl im Chat-UI als Live-Status-Indikator auf ("Archivar sucht …", "Visualizer rendert …") als auch im Debug-View (§16) auf der Agent-Achse.

### Was noch fehlt
- Konsistentes Sub-Agent-Routing über alle Rollen (heute nur ein delegiertes Sub-Agent funktioniert real).
- UI-Sichtbarkeit, **welche** Rolle gerade arbeitet — Lifecycle-Events oben sind die Grundlage, Chat-UI muss sie noch rendern.
- Verschachtelte Delegation (Worker delegiert an Sub-Worker) — siehe Nested Chats §10.

---

## 9. Multi-Postgres-Architektur

**Status:** vorhanden — drei DB-Schichten existieren: `admin_db`, `logging_db`, `tenant_<slug>`.

### Vision
- **admin_db** (Plattform): Tenants, Users, Memberships, Plan/Quota, Plattform-Settings.
- **logging_db** (Plattform): Append-only Audit/Telemetrie. Tagged mit `tenant_id`. Eingrenzbar pro Tenant.
- **tenant_<slug>** (pro Tenant): Alle fachlichen Daten. Mehrere User können sich einen Tenant teilen.
- **Keine FK-Constraints zwischen DBs**: polymorphe Verlinkung über nackte IDs + `target_cls`.

### Was zu klären ist
- Backup/Restore-Strategie pro Tenant (Wechsel des Tenants, Export, Löschung).
- Migration-Story bei Schema-Changes über alle Tenant-DBs gleichzeitig.

---

## 10. Nested Chats / Sub-Chats

**Status:** teilweise — `AiChat` hat bereits `parent_chat_id` / `parent_tool_call_id` / `depth`, aber UI listet nur Top-Level-Chats und es gibt kein systematisches Ergebnis-Hochspülen.

### Vision
- Ein Chat kann **Sub-Chats** öffnen, die fokussiert ein Teilproblem bearbeiten.
- **Ergebnis fließt zurück**: Der Sub-Chat liefert ein zusammengefasstes Ergebnis an den Parent-Chat, ohne den vollen Sub-Chat-Verlauf in dessen Kontext zu spülen.
- **Zweck**: Tiefes Eintauchen ohne Kontext-Fenster-Explosion. Der Hauptmanager bleibt im großen Bild, Sub-Worker arbeiten in eigenen Chats.
- **UI**: Im Chat sichtbar, dass ein Sub-Chat existiert (anklickbar), eventuell linke Spalte als Baum.
- **Chat hängt an einer Resource** — `AiChat` bekommt einen polymorphen Anker (`target_cls` / `target_id`), analog zu `Document`. Damit kann ein Chat (Top-Level oder Sub) explizit "über" einer Resource laufen (Vorgang, Projekt, View, …) und diese Resource zeigt umgekehrt ihre Chats. Siehe §18.

### Sub-Agent-Result-Contract

Wenn ein Sub-Chat sein Ergebnis an den Parent-Chat zurückgibt, geht das **nicht** als voller Sub-Chat-Verlauf und **nicht** nur als freier String, sondern über einen festen Contract:

- **`summary`** (Markdown) — kurzer, menschenlesbarer Bericht, was getan/herausgefunden wurde. Geht in den Parent-Chat-Verlauf als Tool-Ergebnis.
- **`outcome`** (strukturiertes JSON) — die maschinell verwertbaren Ergebnisdaten (gefundene IDs, Werte, Entscheidungen). Wird vom Parent-Agent gelesen, nicht angezeigt.
- **`artifacts`** (Referenzen) — Liste der `ChatArtifact`-Einträge, die im Sub-Chat erzeugt/touched wurden und die der Parent in seine eigene Mappe übernehmen darf (siehe §24).
- **`confidence`** / **`open_questions`** (optional) — Flag wenn der Sub-Agent unsicher ist, mit konkreten Rückfragen an den Parent.

Der Parent-Agent bekommt nur den Result-Contract in seinen Kontext. Der volle Sub-Chat-Verlauf bleibt erhalten und ist über die UI weiterhin einsehbar (Live-Tail während des Laufens, Ergebnis-Karte danach).

### Was zu klären ist
- Hartes Tiefenlimit für Sub-Chat-Nesting vs. Soft-Warnung via Kosten?
- Wie wird ein laufender Sub-Chat im Parent angezeigt — Live-Tail (volle Sicht), Live-Status (nur "läuft noch"), oder nur Ergebnis-Karte am Ende?

---

## 11. Visualisierung

**Status:** teilweise — es gibt einen `visualizer`-Agent, aber kein durchgängiges Rendering-System im UI.

### Vision
- Das Tool kann **visualisieren**, was es bearbeitet:
  - **HTML** — Bot generiert HTML, UI rendert direkt (sandboxed).
  - **SVG** — Diagramme, Abläufe, Vorgangsstrukturen.
  - **Bilder** — z.B. via Image-Generation für Mockups, Skizzen.
- **Use Case Vorgang**: "Zeig mir den Vorgang als Bild" → AI rendert eine Übersichtsgrafik aus den Vorgangsdaten. Nutzer kann sagen: "Update die Phase 2." → AI updatet das Bild.
- Die Visualisierung lebt im Chat oder im Overlay; sie wird als **Artefakt** persistiert (`ChatArtifact` existiert bereits).

### Was noch fehlt
- Sandboxed HTML-Rendering im Chat.
- Inline-SVG-Rendering mit sicherer Sanitization.
- Workflow für "AI generiert Bild → Nutzer kommentiert → AI updatet" (Iterations-Loop).

---

## 12. Adressen, Orte, Personen-Adressbuch

**Status:** fehlt für allgemeine Adressen/Orte — Kontakte existieren im CRM-Layer (`crm/contact.py`, `crm/account.py`).

### Vision
- Eigene Entität **Address** (Strukturiert: Straße, PLZ, Ort, Land + Freitext-Notiz).
- Eigene Entität **Place** (Ort mit Koordinaten oder freier Bezeichnung, z.B. "Hauptlager", "Baustelle Nord").
- Beide polymorph an Vorgang, User, Kunde, Event, Task anhängbar.
- Sollte zusammenspielen mit Karten-Visualisierung später (siehe §11).

---

## 13. Aktionen

**Status:** vorhanden — `Action`-Modell (`lib/actions.py`), Registry (`lib/actions_registry.py`), LLM-Refinement (`lib/actions_refine.py`).

### Vision
- **Aktionen sind das zentrale Kontroll-Element** der UI. Eine Aktion ist ein klickbarer Button mit klarer Wirkung.
- **Scopes:**
  - **Global** — überall verfügbar (z.B. "Neuen Vorgang anlegen").
  - **Pro Chat** — auf den aktuellen Chat-Kontext bezogen ("Zusammenfassen").
  - **Pro Sub-Chat** — innerhalb einer Sub-Arbeit ("Recherche abschließen und hochspülen").
  - **Pro Entität** — auf konkrete Resource ("Diesen User updaten", "Diesen Vorgang archivieren").
- **Vorschlagen**: Die AI schlägt Aktionen kontextabhängig vor. Nutzer kann auch explizit suchen.
- **Bestätigungs-Flow**: Aktionen, die irreversibel oder kostspielig sind (Rechnung versenden, Mail rausgeben), erzeugen erst ein **Draft** und verlangen Bestätigung.
- **Overlay-getrieben**: Klick auf eine Entitäts-Aktion öffnet ein Overlay zur Bearbeitung — nicht eine Vollbild-Maske.

### Was noch zu bauen ist
- Scope "pro Sub-Chat" — gibt's noch nicht klar.
- Draft/Confirm-Pattern als wiederverwendbarer Mechanismus (heute ad-hoc).
- AI-Aktions-Suche, die wirklich raussucht (heute nur Refinement vorhandener Treffer).

---

## 14. Overlays als UI-Stilmittel

**Status:** teilweise — `EntityOverlay`, `DocumentOverlay`, `DiffOverlay`, `ErrorOverlay` existieren.

### Vision
- **Minimalistische UI**: Hauptbild ist der Chat. Alles andere lebt in **Overlays**.
- Vorteile: Kontext bleibt, kein Wegklicken, schneller Wechsel zurück zur Konversation.
- Konsistente Overlay-Patterns: Header mit Resource-Name, Body mit Bearbeitung, Footer mit Aktionen, ESC schließt.
- Stack-fähig: Overlay über Overlay (z.B. Dokument-Overlay öffnet Diff-Overlay).

### Was zu klären ist
- Maximale Overlay-Tiefe / Verlauf-Pfeile?
- Wann Overlay vs. wann Sidebar-Tab?

---

## 15. Admin View

**Status:** fehlt für eine echte Admin-UI — die Daten sind da (`admin_db`, `logging_db`), aber kein dedizierter Admin-View.

### Vision
- Eigener UI-Bereich für Plattform-Betreiber.
- Sicht auf:
  - **admin_db**: Tenants, User, Memberships, Quoten, Status.
  - **tenant_<slug>** pro Tenant: read-only Inspect über alle Entitäten.
  - **logging_db**: gefilterter Audit-Trail pro Tenant, Plattform-Telemetrie.
- Operatives Set: Tenant anlegen/sperren, User reset, Quota anpassen, Debug-Sicht.

---

## 16. Debug View

**Status:** teilweise — `debug_mcp` existiert für DB-Introspektion; es gibt eine `/traces`-Seite. Aber kein vereinigter Debug-View.

### Vision

Der Debug-View ist **bewusst eine eigene UI-Hauptachse** — kein Sammelsurium aus verstreuten Detail-Pages, sondern eine information-dichte, optisch eigenständige Oberfläche, in der man die Plattform live "atmen sieht" und beim Diagnosefall in wenigen Klicks von der fachlichen Beobachtung zum auslösenden LLM-Prompt herunterzoomen kann.

Sichtbar nur für **Tenant-Supporter** und **Plattform-Admin** (siehe Auth-Querschnitt). Reguläre Tenant-User sehen ihn nicht.

### Drei Drilldown-Achsen

Der Debug-View hat drei Einstiegs-Achsen, die alle ineinander verlinken — der Punkt ist, dass man von jeder Achse aus in die anderen springen kann, ohne den Kontext zu verlieren.

**a) Trace-Achse — "was hat dieser Lauf gemacht?"**
- Liste aller Traces, filterbar nach Tenant, Zeit, Status, intent, Tool-Call-Count, Dauer.
- Drilldown pro Trace: Event-Strom (`logging_db.event`), LLM-Request/Response-Paare (mit Prompt-Volltext und Response-Body), Tool-Calls (mit Argumenten und Ergebnis), Sub-Trace-Links rekursiv.
- Cross-Links: vom Tool-Call zur fachlich erzeugten Entität, vom Trace zu allen Change-Log-Einträgen (§26), die in dieser Runde geschrieben wurden.

**b) Entitäts-Achse — "was ist mit dieser Entität passiert?"**
- Einstieg: beliebige Entität (Vorgang, Document, Task, …).
- Tabs pro Entität: **Verlauf** (Change-Log §26, chronologisch), **Fachliche Events** (§2, kuratiert), **Beteiligte Chats** (`AiChat` mit `target_cls`/`target_id`-Anker, §10/§18), **ChatArtifact-Backrefs** (in welchen Chats wurde sie angefasst).
- Jeder Change-Log-Eintrag mit `trace_uid` ist klickbar → springt auf die Trace-Achse.

**c) Agent-/MCP-Achse — "wer kann was, und was läuft gerade?"**
- Liste aller MCPs: Status (online/offline), Endpunkt, Typ (Tool-MCP vs. Sub-Agent-MCP — siehe §21), exponierte Tools, letzte N Calls, Fehler-Quote, Latenz-Quartile.
- Liste aller Manager-/Sub-Agent-Rollen: aktive Sessions live, Tool-Berechtigung pro Rolle, **welche Tools für welchen Tenant freigeschaltet sind** (Feature-Flags / Quotas).
- Live-Tail aller Sub-Agent-Lifecycle-Events (`sub_agent_started/progress/completed`, §8) als Stream.
- Drilldown: aktive Session → der zugehörige Trace, die laufenden Tool-Calls, der Sub-Chat-Baum.

### UI-Anspruch

Anders als die fachliche UI darf der Debug-View **information-dicht** sein — Tabellen mit vielen Spalten, mehrere parallele Panes (Master/Detail/Detail-Detail), Live-Streams, JSON-Treeviews. Inspiriert von Devtools/Profiler-UIs (Jaeger, OpenTelemetry-UI, Datadog-Trace-Explorer), nicht vom Chat. Keyboard-Shortcuts für Navigation. Kopierbare IDs / Trace-UIDs überall.

Tab-Layout grob:
1. **Live** — Echtzeit-Strom aller aktiven Traces und Sub-Agent-Calls.
2. **Traces** — Trace-Achse, durchsuchbar/filterbar.
3. **Entities** — Entitäts-Achse, freier Selector über das gesamte Entity-Universe.
4. **MCPs & Agents** — Agent-Achse mit Tool-Berechtigungs-Matrix.
5. **Change-Log** — globaler Strom aller Entity-Changes (§26), filterbar nach `target_cls`, `actor_type`, `change_type`, Zeit, Tenant.
6. **Errors** — alle `ErrorReport` + `error`-Events der letzten 24h.

### Abgrenzung zur Admin View (§15)

- **Admin View** = Plattform-Betrieb: Tenants anlegen, User sperren, Quoten setzen, Memberships managen. Operative Mutation.
- **Debug View** = Diagnose: read-mostly, drilldown-orientiert, "was ist passiert und warum". Nicht zum Eingreifen, sondern zum Verstehen.

Beide bleiben getrennte UIs.

---

## 17. Klassische Funktionalitäten neben AI

**Status:** teilweise.

### Vision
- AI ist das Hauptinteraktions-Mittel, aber **klassische deterministische Funktionen müssen vorhanden bleiben**:
  - Task abhaken
  - Dokument speichern / Version restoren / Diff anzeigen
  - Datei runter-/hochladen
  - Suche (semantisch und exakt)
  - Filter/Sortierung in Listen
- Diese Funktionen sind über die UI direkt zugänglich, **ohne** dass der Chat zwingend involviert sein muss.
- Die generische Such-/Filter-/Listen-Oberfläche für all das ist der **Explorer** (§18).

---

## 18. Explorer — universeller Entity-Navigator mit Views

**Status:** fehlt komplett.

> Arbeitstitel **Explorer**. Die endgültige Bezeichnung (`Explorer`, `Büro`, `Hub`, `Workspace`, …) wird später festgelegt. Bewusst **nicht** "Wiki", weil das mit `Document` kollidieren würde.

### Vision

Der Explorer ist die **zweite Hauptachse der UI** neben dem Chat: links die Sessions, rechts der Explorer. Eine einzige Oberfläche, über die der Nutzer das gesamte Entity-Universum des Tenants durchsuchen, filtern, sortieren und gruppieren kann — manuell und ohne den Umweg über die AI.

Der Chat ist die **conversational** Arbeitsachse ("sende dem Mitarbeiter eine Nachricht", "schreibe eine Rechnung"). Der Explorer ist die **strukturelle** Arbeitsachse für die Momente, in denen der Nutzer selbst suchen, vergleichen oder eine Übersicht haben will ("gib mir alle Rechnungen", "was wurde diese Woche bearbeitet").

### Drei Bausteine

1. **Entity-Universe** — die Gesamtheit aller polymorphen Entitäten im Tenant. Existiert implizit über alle `BaseMixin`-Tabellen.
2. **View** — eine gespeicherte Spezifikation, die aus dem Universe einen Ausschnitt baut und als Liste, Baum oder gruppierte Tabelle darstellt.
3. **Action-Surface** — die kontextabhängigen Aktionen, die an einer View, einem Knoten oder einer Entität hängen (siehe §13).

### View-Typen

**a) Dynamische View** — eine gespeicherte Query.
- Spec ≈ `{filter, groupBy[], sortBy[], columns[]}`.
- Inhalt wird **nicht persistiert**, sondern bei jedem Öffnen neu evaluiert.
- Beispiele: "alle Rechnungen, gruppiert nach Monat dann nach Mitarbeiter", "alle Tasks, mir letzte Woche zugewiesen", "Vorgänge mit Status offen, sortiert nach Alter", "alles, was in der letzten Woche bearbeitet/angelegt wurde".
- Standard-Vorlagen ("zuletzt bearbeitet", "neu angelegt diese Woche") sind einfach vorinstanzierte dynamische Views.

**b) Kuratierte View** — ein hand-gebauter Baum.
- Jeder Knoten ist entweder eine **Referenz auf eine Entität**, ein **Ordner** oder eine **Sub-View** (siehe c).
- Inhalt ist **explizit persistiert** und ändert sich nicht automatisch.
- Beispiele: "meine Top-Vorgänge des Quartals", themenbezogene Sammlungen, geteilte Dossiers.

**c) Hybrid** — kuratierter Baum mit dynamischen Sub-Views als Knoten.
- Beispiel: ein Quartals-Dashboard, in dem ein Knoten "alle offenen Tasks meines Teams" ein Live-Filter ist.
- Mächtig, aber komplex — wird **nicht in V1** gebaut.

### Views als Entitäten

Eine View ist eine **reguläre Tenant-Entität** (`@register_entity("core.view")`), mit Name, Beschreibung, Spec (JSON), Sichtbarkeit und Owner. Konsequenzen:
- Views tauchen automatisch im Entity-Universe auf → es kann eine View über Views geben ("alle Views, die letzte Woche bearbeitet wurden").
- Views können polymorph an Projekten/Vorgängen hängen (typisch: ein Vorgangs-Dashboard).
- Versionierung wie beim `BaseMixin`-Pattern; bei Bedarf später `ViewVersion` analog zu `DocumentVersion`.

### Rekursion: Link statt Auto-Expansion

Eine View, die eine andere View als Knoten enthält, **expandiert nicht automatisch**. Stattdessen wird der Sub-Baum erst auf expliziten Klick geladen — UI zeigt einen Link / Disclosure-Toggle. Begründung: ohne diese Disziplin würde eine "View aller Views" einen unendlichen Render-Loop bauen.

### Chat ↔ View

Die beiden UI-Achsen sollen sich überlappen, nicht parallel laufen:

- **Chat lebt auf einer Resource** — `AiChat` bekommt einen polymorphen Anker (`target_cls` / `target_id`), analog zu `Document` (siehe §10). Damit kann ein Chat explizit "über einer View" (oder über einem Vorgang, Projekt, …) geführt werden.
- **View zeigt ihre Chats** — die Detail-Ansicht einer View hat eine Tab-Sektion "Chats", einfach `select * from ai_chat where target_cls='core.view' and target_id=?`.
- **Chat spawnt Views** — eine Aktion im Chat legt einen `View`-Datensatz an, der als `ChatArtifact` im Chat eingebettet wird (das Pattern existiert schon, siehe `chat_artifact.py`). Klick öffnet das Overlay mit der View (§14).
- **Chat bearbeitet Views** — der Nutzer kann der AI sagen "mach die Sortierung nach Mitarbeiter", die AI editiert die View-Spec, das Artifact aktualisiert sich live.

Diese polymorphe Erweiterung von `AiChat` ist **nicht Explorer-exklusiv** — sie macht auch die Sub-Chats aus §10 sauberer (Sub-Chat hängt explizit an der Resource, an der er arbeitet).

### Sichtbarkeit: rollenabhängig

Nicht jede Tabelle gehört in jeden Explorer. Sichtbarkeit hängt an der **Rolle des Aufrufers**:

- **Tenant-Administrator und Mitarbeiter** sehen nur **fachliche Entitäten** (Projekt, Vorgang, Task, Document, Note, Comment, Contact, Account, Workflow, Memory, View, …).
- **Tenant-Supporter** (siehe Auth-Querschnitt) sieht zusätzlich **interne Entitäten** (`SemanticSnippet`, `AiToolCall`, `AiMessage`, `ChatArtifact`, …), um beim Tenant reingucken und Support leisten zu können.
- **Plattform-Admin** (siehe §15) hat eigene Explorer-Rechte, die auch `admin_db` und `logging_db` abdecken.

Realisierung: pro `@register_entity` ein `explorer_scope`-Marker (Enum: `fachlich`, `intern`, `support_only`, `hidden`).

### Permissions: Spec geteilt, Evaluation pro Aufrufer

Eine View ist tenant-weit teilbar — die zurückgelieferten Daten sind aber **pro Aufrufer gefiltert**. Beispiel: View "alle Tasks, gruppiert nach Assignee" zeigt für User A nur Tasks, die A sehen darf; User B sieht andere Reihen. **Die Spec bleibt eine; die Evaluation respektiert die Berechtigungen des Aufrufers.**

### Aktionen — drei Scopes

Orthogonal zu §13, aber konkret im Explorer-Kontext:
- **Entity-Action** — kommt aus dem Typ des Knotens (z.B. Vorgang → "archivieren"). Standard pro Entity-Typ.
- **View-Action** — kommt aus der View selbst (z.B. "als CSV exportieren", "View teilen", "neue Sub-View hieraus bauen", "Chat über diese View starten").
- **Node-Action** — kommt aus der konkreten Knoten-Konfiguration in einer kuratierten View (z.B. "Knoten umbenennen", "Knoten entfernen").

### View-Spec: strikt typisiertes JSON

Damit die Spec deterministisch evaluierbar **und** AI-generierbar (Tool-Call mit Schema, kein Halluzinations-Risiko) ist, ist sie strikt typisiertes JSON. Grobe Struktur (Entwurf, beim Implementieren festzulegen):

```json
{
  "kind": "dynamic" | "curated",
  "entityTypes": ["core.task", "core.document"],
  "filter": { ... },
  "groupBy": [ { "field": "...", "order": "asc" } ],
  "sortBy":  [ { "field": "...", "order": "desc" } ],
  "columns": [ ... ],
  "nodes":   [ ... ]   // nur bei curated
}
```

### Verhältnis zu bestehenden Konzepten

- **§3 Notizen/Dokumente/Anhänge/Kommentare** — der Explorer ist die Such-/Listen-Oberfläche, in der diese Entitäten gefunden werden. Editieren passiert weiterhin im Overlay (§14).
- **§10 Nested Chats** — `AiChat` bekommt einen polymorphen Anker; das ist eine Voraussetzung für die Chat-View-Kopplung und gleichzeitig ein Architektur-Gewinn für Sub-Chats.
- **§13 Aktionen** — der Explorer ist eine prominente neue Action-Surface mit drei Scopes (Entity / View / Node).
- **§14 Overlays** — Klick auf einen Knoten öffnet das jeweilige Entity-Overlay; Klick auf "Sub-View expandieren" öffnet die Sub-View entweder inline oder als Overlay.
- **§17 Klassische Funktionalitäten** — Filter/Sortierung/Listen-Browsing ist genau das, was der Explorer als Default-UX liefert.

### Was zu klären ist
- Endgültiger Name (`Explorer`, `Büro`, `Hub`, `Workspace`?).
- Konkretes JSON-Schema für die View-Spec.
- Wie geht eine View mit **gemischten Entity-Typen** um (eine Liste, in der Tasks und Dokumente nebeneinander stehen — gemeinsame Spalten oder pro Typ eigene Darstellung)?
- AI-Aktion "View vorschlagen": wann/wo schlägt die AI proaktiv eine View vor ("du arbeitest gerade an Vorgang X, willst du eine Übersicht über ähnliche Vorgänge")?

---

## 19. Notifications

**Status:** fehlt komplett.

### Vision
- Eine **Notification** ist eine eigene Tenant-Entität: Empfänger, Quelle (Entity-Ref), Typ, Text, Zeitpunkt, Read-State.
- **Keine separate Inbox-UI.** Notifications werden über den Explorer (§18) konsumiert — eine Default-View "ungelesene Notifications" plus filterbar nach Typ/Quelle/Zeit/gelesen-Status.
- "Als gelesen markieren" ist eine reguläre Entity-Action (§13), kein Spezial-Mechanismus.
- Filter "nur Mentions", "nur AI-Hinweise", "gelesen ausblenden" sind einfach gespeicherte Views.

### Begründung gegen Inbox-UI
Eine prominente Inbox erzeugt Druck und Notification-Fatigue. Indem Notifications nur eine View unter vielen sind, entscheidet der Nutzer aktiv, wann er hinschaut, und kann sich seine eigene Sicht (Prio-Filter, AI-Lärm raus, nur Vorgang X) bauen.

### Quellen (Auswahl)
- @-Mention in Comment / Note / Chat-Reply
- Task an mich assignt, Status-Wechsel an Vorgang, an dem ich beteiligt bin
- AI-Worker hat Sub-Task abgeschlossen / Action-Draft wartet auf Bestätigung
- ExternalEvent (§20) hat den Status meines Vorgangs verändert
- Reminder (§23) ist fällig geworden

### Was zu klären ist
- Routing: bekommt jeder beteiligte User dieselbe Notification, oder gibt es Prio/Empfänger-Auswahl?
- AI-Lärm-Limit: darf der Manager-Agent selbst Notifications erzeugen, und wie verhindern wir Spam?
- Eskalations-Layer (Mail-Digest, Push) — bewusst später, kommt mit externer Integration (§20).

---

## 20. Externe Integrationen (Mail, Kalender, …)

**Status:** fehlt komplett.

### Vision
Externe Welten (Mail, Kalender, Telegram, Notion, Drittsystem-APIs) werden über **MCPs** (§21) angebunden. Die externen Daten landen als **eigene Tenant-Entitäten** — nicht als ad-hoc-Strings im Chat — und werden damit durchsuchbar, semantisch indexierbar, polymorph anhängbar.

### Mail
- **Eigene Entität `Mail`** in der Tenant-DB: Richtung (in/out), Absender, Empfänger, Subject, Body, Status (`received` / `sent` / `failed`), Send-/Receive-Timestamp, Thread-Referenz.
- **Anhänge** werden als `Attachment` (existiert) angelegt, polymorph an die Mail gehängt; die Files landen im normalen Datei-Storage.
- **Eingehende Mail** wird zum fachlichen Event (§2) am betreffenden Vorgang/Projekt, sofern zuordenbar (AI versucht Match anhand Subject / Adresse / Thread / Kunde).
- **Ausgehende Mail** wird über eine Action (§13) erzeugt, durchläuft den Draft/Confirm-Flow, geht über den Mail-MCP raus.

### Kalender
- **Eigene Entität `Appointment`**: Titel, Beschreibung, Beginn/Ende, Ort (verknüpfbar mit `Place`, §12), Teilnehmer, externer Cal-Sync-Status.
- Polymorph anhängbar (am Vorgang, am Projekt, am Kunden).
- Zwei-Wege-Sync mit Outlook/Google über den Calendar-MCP.

### `ExternalEvent` — Audit-Spur nach aussen
Eigene Entität für **alles, was vom System aus an die Aussenwelt ging oder bei einem Drittsystem etwas verändert hat**.
- Beispiele: gesendete Mail (mit Backreference auf `Mail`), gesendete Telegram-Message, Notion-Page-Update, Webhook-Call zu einem Drittsystem.
- Felder: Zeitpunkt, Auslöser (User oder Agent), Ziel-System, Aktion, Payload-Referenz, Erfolg/Failure-Status.
- Wichtig für **Auditierbarkeit** und für Übersichts-Views ("was wurde heute alles rausgeschickt?", "alle gescheiterten Auslieferungen letzte Woche").

### Abgrenzung
- **`Event`** (§2) — fachlich, am Vorgang ("Kunde hat sich gemeldet").
- **`ExternalEvent`** (§20) — "wir haben mit der Aussenwelt geredet" (Audit + Übersicht).
- **`Mail` / `Appointment`** — die konkreten Payload-Entitäten.

Default beim Mail-Versand: **beides** wird erzeugt — `Mail` (die Sache), `ExternalEvent` (Audit), und ein fachliches `Event` am Vorgang, das auf beide referenziert.

### Was zu klären ist
- Welche externen Systeme sind V1 (vermutlich nur Mail), welche kommen später?
- IMAP/SMTP direkt oder via Provider-API (Gmail/Outlook OAuth)?

---

## 21. MCP-Architektur

**Status:** teilweise — MCPs existieren (`mcp_servers/`), aber ohne formales Manifest, ohne Self-Description, ohne UI-Erweiterungs-Mechanismus.

### Vision
MCPs sind die **Plug-in-Schicht für fachliche Domänen und externe Integrationen**. Eine Domäne ohne MCP gibt es nicht — die Hauptanwendung weiß generisch nichts über "Rechnungen", "Mails" oder "Reklamationen"; sie kennt nur `Entity`, `View`, `Action`, `Chat`, `Overlay`. Domain-Wissen lebt im jeweiligen MCP.

**Konsequenz:** Die Hauptanwendung bleibt **domänen-agnostisch** und in unterschiedlichen Branchen einsetzbar. Neue Branchen kommen durch das Austauschen oder Hinzufügen von MCPs rein, nicht durch Änderungen am Core.

### MCP-Kind: Tool-MCP vs. Sub-Agent-MCP
MCPs werden explizit nach ihrer Rolle unterschieden — die Hauptanwendung und der Debug-View (§16) brauchen diese Information, um sinnvoll routen und visualisieren zu können.

- **Tool-MCP** (`kind: "tool"`) — passiver Werkzeug-Anbieter. Stellt Funktionen bereit, die ein Agent direkt aufruft (DB-Zugriff, Mail-Versand, Lookup). Stateless aus Agent-Sicht. Beispiele heute: `crm_mcp`, `debug_mcp`, `mock_mcp`.
- **Sub-Agent-MCP** (`kind: "sub_agent"`) — der MCP ist Wrapper um einen oder mehrere autonome Sub-Agents. Ein Aufruf erzeugt einen eigenen Sub-Chat (§10), eigenes LLM-Kontextfenster, Result-Contract als Antwort. Beispiele in der Vision: `archivar`, `web_researcher`, `visualizer`, `coach`, `sales_support`.
- **Mixed** (`kind: "mixed"`) — bietet beides; muss pro Tool deklarieren, ob es ein passives Tool oder ein Sub-Agent-Spawn ist (`tool_kind: "function" | "sub_agent"`).

**Konsequenzen:**
- Der Manager-Agent weiß beim Tool-Call sofort, ob er einen Sub-Chat anlegen und den Result-Contract erwarten muss.
- Der Debug-View listet beide Typen klar getrennt: "MCPs (passiv)" vs. "Sub-Agent-Rollen (aktiv)".
- Lifecycle-Events (§8) feuern nur für Sub-Agent-MCPs.
- Quotas / Kostenrechnung können nach Kind unterschiedlich tarifiert werden (Sub-Agent-Calls sind teurer).

### Self-Description / Manifest
Jeder MCP exponiert ein **Manifest**, das maschinell lesbar und einbindbar ist:

- **kind** — `tool` / `sub_agent` / `mixed` (siehe oben).
- **Beschreibung** — was der MCP tut, für welche Use-Cases.
- **Bereitgestellte Tools** — Liste mit Inputs/Outputs; bei `mixed` pro Tool das `tool_kind`.
- **Verwaltete Entitäten** (`@register_entity`) — welche Entity-Typen kommen aus diesem MCP.
- **Abhängigkeiten** — benötigte Entitäten/MCPs anderer Module ("Ich brauche `Contact` aus dem CRM-MCP, ich brauche `Mail.send` vom Mail-MCP").
- **Berechtigungen** — welche Tools dieser MCP aus anderen MCPs aufrufen darf.
- **UI-Erweiterungen** — optionale Overlays/Actions, die der MCP bereitstellt (siehe unten).

### MCP-administrierte Sub-Agents
Ein MCP kann **selbst Agents managen** — nicht nur dumme Tools anbieten, sondern weitere Sub-Agents oder Sub-MCPs orchestrieren. Beispiele:
- **HR-MCP** startet einen Recruiter-Sub-Agent und einen Onboarding-Sub-Agent.
- **Research-MCP** spawnt mehrere parallele Web-Researcher-Sub-Agents.

Das ist die strukturelle Vertiefung des virtuellen Büros (§8): das Büro hat nicht nur Mitarbeiter, sondern auch Abteilungsleiter, die eigene Teams führen.

### MCP-bereitgestellte UI / Overlays
Wenn ein MCP eine Entität verwaltet, soll er die **Edit-UI selbst stellen können**. Die Hauptanwendung muss nicht wissen, wie man eine `Rechnung` editiert.

Konkret:
- Der MCP registriert eine UI-Erweiterung im Manifest (z.B. sandboxed iFrame / Micro-Frontend).
- Klick auf "Rechnung editieren" öffnet das vom Rechnungs-MCP gelieferte Overlay im normalen Overlay-Stack (§14).
- Hauptanwendung rendert den Container, der MCP rendert den Inhalt.

### Was zu klären ist
- Manifest-Format (JSON-Schema-File pro MCP? Endpunkt am MCP, das das Manifest zurückgibt?).
- UI-Erweiterungs-Protokoll: iFrame + postMessage? WebComponent? Eigenes Schema?
- MCP-Discovery: statische Registry vs. dynamisch zur Laufzeit?
- Sandboxing-Modell für MCP-UIs (CSP, Permission-Limits) — Detail kommt mit Sicherheits-Runde.

---

## 22. Tags

**Status:** teilweise — `Tag` und `TagAssignment` existieren als Entitäten, aber kein Konzept im Vision-Doc.

### Vision
- Tags sind eine **leichtgewichtige, orthogonale Kategorisierung** über jede Entität: Vorgang, Document, Task, Mail, Appointment, View — alles taggbar.
- Tags werden im Explorer (§18) als Filter und Gruppierung unterstützt ("alle Vorgänge mit Tag `urgent`").
- Tags sind **tenant-weit** (geteiltes Vokabular), nicht per User.

### AI- vs. Mensch-Tagging
Jede `TagAssignment` trägt einen Marker, **wer das Tag gesetzt hat**: `human` (mit User-Ref) oder `ai` (mit Agent-Ref).

- Sichtbar in der UI — z.B. unterschiedlicher Style für AI-Tags.
- Filterbar im Explorer ("nur Tags, die ich selbst gesetzt habe", "AI-Vorschläge").
- Begründung: AI-Tags sollen vorschlagen, nicht autoritativ wirken. Der Nutzer soll auf einen Blick sehen, was vom System kommt, und schnell bestätigen oder entfernen können.

### AI nutzt Tags
- AI kann anhand vorhandener Tags Suche/Filterung präzisieren.
- AI kann Tags als strukturierte Klassifikations-Outputs setzen ("Diese Mail ist `reklamation`").
- AI kann **neue Tags vorschlagen** — die landen aber zunächst als Draft, ein Mitarbeiter oder Admin approved sie ins Vokabular.

### Was zu klären ist
- Tag-Hierarchie (`reklamation/anwalt`) oder flach mit Konvention?
- Lebenszyklus: wer darf Tags umbenennen/löschen, was passiert mit den Assignments?

---

## 23. Reminders

**Status:** teilweise — `Reminder` existiert als Entität, aber ohne Konzept.

### Vision
Reminders sind **zeitgesteuerte Trigger**, die auf zwei Adressaten zielen können — Mensch oder AI.

### Mensch-Reminder
- Klassischer "erinnere mich um X an Y".
- Erzeugt zum fälligen Zeitpunkt eine Notification (§19).
- Polymorph anhängbar (am Vorgang, am Document, am Kunden).

### AI-Reminder (Cron-artig, Worker-getrieben)
- Der Reminder feuert **nicht in Richtung Mensch, sondern triggert einen Agenten/Worker** aus dem virtuellen Büro (§8).
- Beispiele:
  - "Alle 5 Wochen: Archivar-Agent prüft, ob dieses Dokument noch aktuell ist, und schlägt ein Update vor."
  - "Jeden Montag 8:00: Sales-Support-Agent fasst die offenen Deals zusammen."
  - "30 Tage nach Vorgangs-Anlage: Coach-Agent checkt, ob alle Milestones realistisch sind."
- Spec eines AI-Reminders: Trigger (cron / einmalig / Bedingung), Ziel-Agent, Prompt-Template, Output-Behandlung (Notification / Comment am Vorgang / neuer Sub-Chat).
- **Menschen können solche AI-Reminder anlegen** — als Aktion pro Entität.
- **AI kann sich selbst Reminder setzen** — z.B. "ich frage in 7 Tagen nochmal nach, wenn der Kunde sich nicht meldet".

### Abgrenzung zu Workflow (§7)
- **Workflow** beschreibt einen Geschäftsprozess.
- **Reminder** ist ein punktueller Trigger, kein Prozess.
- Ein Workflow-Schritt kann Reminders erzeugen, aber Reminders existieren auch unabhängig.

### Was zu klären ist
- **Quota** für AI-Reminders pro Tenant — sonst Kosten-Explosion durch unkontrollierte Cron-Jobs.
- Wer hält den Cron-Scheduler — eigener Service-Process oder im Gateway?
- Versions-Drift: was, wenn der Reminder einen Agent ruft, dessen Tool-Set sich inzwischen verändert hat?

---

## 24. ChatArtifact — Mappe pro Chat

**Status:** vorhanden — `ChatArtifact` existiert (`chat_artifact.py`), wird aber im Vision-Doc nicht erklärt.

### Vision
`ChatArtifact` ist die **Mappe pro Chat**: jede Entität, die im Chat **hochgeladen, gelesen, erzeugt, geklont oder manuell verlinkt** wurde, bekommt eine Zeile in dieser Mappe. Die `relation` kategorisiert die Herkunft (`uploaded`, `touched`, `created`, `cloned`, `linked`).

### Wofür gut
- **UI** — die Chat-Sidebar zeigt "Was wurde in diesem Chat angefasst?", direkter Sprung zu jeder beteiligten Entität.
- **AI-Kontext** — vor jedem LLM-Call kann der Agent kompakt die Mappe einlesen, ohne den vollen Tool-Call-Verlauf zu parsen.
- **Audit** — "diese Rechnung wurde im Chat #4711 erzeugt".
- **Klon-Mechanik** — ein neuer Chat erbt mit Relation `cloned` Auszüge aus der Mappe des Parent-Chats.
- **Sub-Chat-Result** — Sub-Chats geben ihre relevanten Artifacts über den Result-Contract (§10) an den Parent zurück, der sie in die eigene Mappe übernimmt.

### Verhältnis zum polymorphen Chat-Anker
- **Chat-Anker** (`AiChat.target_cls` / `target_id`, §10/§18) = "dieser Chat **gehört zu** dieser einen Resource". 1:1.
- **ChatArtifact** = "diese Entitäten wurden **im Chat angefasst**". M:N, kategorisiert.
- Die beiden Mechaniken sind orthogonal und werden zusammen genutzt.

### Sichtbarkeit
- `ChatArtifact` ist eine **interne Entität** — Tenant-Mitarbeiter sehen sie nicht direkt im Explorer, Tenant-Supporter schon (siehe Auth-Querschnitt, §18).
- Die fachliche Sicht ist die Chat-Sidebar, nicht eine eigene Explorer-View.

---

## 25. Sharing-Links

**Status:** fehlt komplett.

### Vision
Inhalte (View, Document, Vorgang, Mail, Appointment, …) können über **Sharing-Links** mit unterschiedlichen Scopes geteilt werden — intern wie extern.

### Zwei Scopes
- **Team-Shared** — sichtbar für alle Mitglieder des Tenants, optional eingeschränkt auf Rollen. Default-Modus für interne Zusammenarbeit.
- **Public-Shared** (extern) — sichtbar für Aussenstehende ohne Account, via Token-URL. Optional mit Passwort, Ablaufdatum, Permission-Stufe (read-only / comment / edit).

### Eigene Entität `Share`
- `target_cls` / `target_id` (welche Entität), `scope` (`team` / `public`), `token`, `password` (optional), `expires_at` (optional), `permission`, `created_by`.
- Polymorph anhängbar — der Share gehört zur geteilten Entität.
- Aktivität auf öffentlichen Shares (Aufrufe, externe Kommentare) erzeugt Notifications (§19) und landet als Event/`ExternalEvent` (§2/§20).

### UI
- Aktion "Teilen" pro Entität öffnet ein Sharing-Overlay (§14) mit Team/Public-Tabs.
- Bei Public-Share: Tab "Aktivität" zeigt, wer wann reingeguckt oder kommentiert hat.

### Was zu klären ist
- Granularität pro Entity-Typ — alles teilbar, oder explizite Allow-Liste pro `@register_entity`?
- Identität externer Kommentatoren: Pseudo-Account, nur Name+Mail, oder Login via Magic-Link?
- Token-Widerruf-Modell: hartes Revoke vs. Reset-Token vs. Generation-Counter?

---

## 26. Change-Log — Audit-Trail pro Entität

**Status:** fehlt komplett. Aktuell zeigt `BaseMixin` nur den letzten Stand (`created_at`, `updated_at`); es gibt keine Historie, wer wann welches Feld auf welchen Wert gesetzt hat. `DocumentVersion` ist die Ausnahme für Dokumente, aber **kein** generisches Pattern.

### Vision

Jede Entität, die `BaseMixin` erbt, bekommt automatisch einen **append-only Change-Log** in `logging_db.entity_change`. Damit ist für **jede** Feldänderung auf **jeder** Entität nachvollziehbar:

- Wer hat die Änderung ausgelöst (Mensch, AI-Agent, System-Job)?
- Wann?
- In welchem Trace (Chat-Runde) ist sie entstanden?
- Welche Felder haben sich von welchem alten auf welchen neuen Wert geändert?
- War es ein `create`, `update`, `delete` oder `soft_delete`?

### Datenmodell

Eigene Entität `EntityChange` in `logging_db` (analog zu `Trace`/`Event`):

```text
tenant_id        str       — zur Tenant-Eingrenzung
target_cls       str       — z.B. "core.task", "core.project"
target_id        int       — die ID der geänderten Entität
change_type      str       — "create" / "update" / "delete" / "soft_delete"
actor_type       str       — "human" / "ai" / "system"
actor_id         int       — User-ID oder Agent-ID (0 wenn system)
agent_name       str       — bei AI: "manager", "sales_support", … (sonst leer)
trace_uid        str       — Brücke zu logging_db.trace (leer bei rein deterministischen Calls)
field_diffs      jsonb     — Liste [{field, old, new}], leer bei create/delete
summary          str       — kurzer Satz, menschenlesbar ("Status von 'offen' auf 'wartet' gesetzt")
created_at       datetime  — Zeitpunkt der Änderung
```

### Granularität: 1 Eintrag pro logischem Vorgang

Ein logischer Save (ein Tool-Call, ein UI-Klick "Speichern", ein Workflow-Schritt) erzeugt **genau einen** `EntityChange`-Eintrag, auch wenn 3 Felder gleichzeitig geändert wurden. Die einzelnen Feld-Diffs landen als Liste in `field_diffs`. Begründung: Sonst zerfällt eine zusammengehörende Änderung in mehrere Reihen, und der Verlauf wird unleserlich.

### Eintragsweg

Automatisch über SQLAlchemy-Event-Hooks (`before_update`, `after_insert`, `after_delete`) am `BaseMixin`. Der aktuelle Aufruf-Kontext (User, Agent, Trace) wird über einen ContextVar gesetzt, den Gateway und Agent vor jeder Operation füllen. Damit muss **kein** einzelner Code-Pfad daran denken, manuell ins Change-Log zu schreiben.

Bei AI-Änderungen schreibt der Agent zusätzlich den `summary`-Text vor (z.B. "Beschreibung um Reklamationsdetails ergänzt"). Bei menschlichen UI-Speicherungen wird er aus einer Default-Vorlage generiert ("3 Felder geändert: status, priority, due_at").

### UI: Verlaufs-Tab pro Entität

Jedes Entity-Overlay (§14) bekommt einen Tab **"Verlauf"** — gefilterte Sicht auf `EntityChange WHERE target_cls=X AND target_id=Y ORDER BY created_at DESC`:

- Pro Eintrag: Wer, Wann, Was (`summary`), Klick auf Detail zeigt die Feld-Diffs (alter Wert ↔ neuer Wert, mit Diff-Markup bei Texten).
- Bei AI-Einträgen: Klick auf `trace_uid` öffnet den Debug-View (§16) auf der Trace-Achse beim auslösenden LLM-Run.
- Farbliche Unterscheidung `human` / `ai` / `system` (analog zu §22 Tags).
- Filter "nur AI-Änderungen", "nur Status-Wechsel", "in der letzten Woche".

### Abgrenzung

- **Change-Log** (`logging_db.entity_change`) — generisch pro Feld-Diff, append-only, **maschinelle Buchhaltung**.
- **Fachliche Events** (`tenant_db.event`, §2) — kuratierte Timeline-Einträge ("Anruf am 12.6.", "Reklamation eingegangen"), **menschliche Erzählung**.
- **DocumentVersion** — bleibt für Dokumente bestehen, weil dort der vollständige Inhalt versioniert wird, nicht nur Feld-Diffs.
- **Logging-Events** (`logging_db.event`) — Telemetrie pro Chat-Runde (Tool-Calls, LLM-Roundtrips), nicht pro Entität.

Ein automatischer Generator kann aus bestimmten Change-Log-Einträgen ein fachliches Event erzeugen — z.B. jedes `status`-Feld-Update am Vorgang erzeugt ein "Statuswechsel"-Event in der Timeline. Welche Felder das auslösen, ist pro Entity-Typ konfigurierbar (siehe Entity-Settings, §27).

### Performance / Aufbewahrung

- `logging_db` hat keine FK auf andere DBs, ist also unabhängig migrierbar / archivierbar.
- Index auf `(tenant_id, target_cls, target_id, created_at desc)` — der Default-Zugriffspfad.
- Aufbewahrungs-Strategie pro Tenant konfigurierbar (Plattform-Settings, §27) — z.B. "unbegrenzt", "12 Monate", "nach Export löschen".
- Für sehr schreib-intensive Tabellen (z.B. `SemanticSnippet`) kann ein Entity-Typ pro `@register_entity` ein Flag `change_log: false` setzen, das die Erfassung abschaltet (interne Tabellen, die kein Audit brauchen).

### Was zu klären ist

- Tiefe der `field_diffs` bei großen Text-Feldern (Beschreibung, Body) — voller alter+neuer Text oder Diff-Snippet?
- Wie verhalten sich Bulk-Operationen (z.B. "alle Tasks dieses Vorgangs schließen") — ein Eintrag pro Task oder ein gebündelter Bulk-Eintrag mit Liste?
- Wie binden wir das in den Semantic-Index? Soll `summary` semantisch durchsuchbar sein ("wann hat AI an diesem Vorgang den Status geändert")?

---

## 27. Settings-Hierarchie — Plattform / Tenant / Entity / Chat

**Status:** fehlt komplett. Es gibt heute keine generische Stelle, an der Verhalten konfiguriert werden kann — alles ist hardcoded oder pro Modul ad-hoc.

### Vision

Settings sind **gestapelte, vererbende Konfigurationsschichten**, die alle Plattform-Verhalten parametrisieren. Eine konkrete Frage ("soll diese AI-Änderung sofort wirksam sein oder als Draft warten?") wird über die Schichten in fester Reihenfolge resolved.

### Vier Schichten

Vom Großen ins Kleine (genau wie Memory §6 und aus demselben Grund: spezifischer überschreibt allgemeiner):

1. **Plattform-Settings** — global für die gesamte Plattform-Installation. Vom Plattform-Admin gesetzt. Hardcoded-Defaults für alle Tenants. Beispiel: "Maximale Sub-Chat-Tiefe = 5", "Standard-Modell = gpt-5.5", "Retention für `entity_change` = 12 Monate".
2. **Tenant-Settings** — pro Tenant, vom Tenant-Admin gesetzt. Beispiel: "Wir nutzen kein gpt-4-Audio", "AI-Reminder erlaubt = ja", "Standard-Sprache = Deutsch".
3. **Entity-Settings** — pro Entity-Typ ODER pro Entity-Instanz (eine konkrete Reihe). Beispiel: "Für diesen Vorgang gilt: AI-Änderungen immer als Draft", "Für Entity-Typ Document: Versionierung an".
4. **Chat-Session-Settings** — pro Chat. Beispiel: "In diesem Chat darf AI Aktionen nicht selbst ausführen, nur vorschlagen", "Sub-Agent-Spawn deaktiviert".

### Resolution: spezifischer gewinnt

Eine Setting-Frage wandert die Schichten von unten nach oben (Chat → Entity → Tenant → Plattform). Das erste **explizit gesetzte** Resultat gewinnt. Plattform liefert immer einen Default — nichts kann ungesetzt sein.

Beispiel zur Frage "AI-Feldänderung direkt oder Draft?":
- Plattform-Default: `direct` (sonst wäre die Plattform unbedienbar).
- Tenant kann auf `draft_for_critical_fields` umstellen (eine Liste von Feldnamen).
- Entity (ein konkreter VIP-Vorgang) kann auf `draft` für alle Felder gehen.
- Chat-Session kann temporär auf `direct` zurückschalten, wenn der User explizit sagt "mach mal schnell".

### Datenmodell

Eine generische `Setting`-Entität (in der jeweiligen DB), polymorph an die Schicht-Quelle gehängt:

```text
scope          str       — "platform" / "tenant" / "entity_type" / "entity" / "chat"
scope_id       str|int   — leer bei platform; tenant_slug; entity-alias; target_id; chat_id
key            str       — z.B. "ai.changes.mode"
value          jsonb     — beliebige strukturierte Werte (bool, string, dict, list)
set_by         int       — User-ID
created_at     datetime
```

**Wo lebt die Tabelle?**
- Plattform-Settings: `admin_db.setting`.
- Tenant- / Entity-Type- / Entity- / Chat-Settings: `tenant_db.setting` (eine Tabelle, scope unterscheidet).

### Resolver

Ein zentraler Resolver `settings.resolve(key, *, tenant, entity_cls=None, entity_id=None, chat_id=None) -> value` macht die Schicht-Suche. Alle Plattform-Module rufen ausschließlich diesen Resolver — niemand bastelt eigene Fallback-Logik.

### Use-Cases (eine wachsende Liste)

- **AI-Änderungs-Modus** — `ai.changes.mode` = `direct` | `draft` | `draft_for_critical_fields` (siehe §26).
- **Sub-Agent-Spawn-Erlaubnis** — `agent.sub_agent.enabled` = `true` | `false`.
- **Max. Sub-Chat-Tiefe** — `agent.sub_chat.max_depth` = `int`.
- **Default-Modell** — `agent.model.default` = `string`.
- **Memory-Token-Limit pro Scope** — `memory.tenant.max_tokens` = `int`.
- **Retention Change-Log** — `audit.change_log.retention_days` = `int`.
- **Workflow-Versionierung** — `workflow.versioning` = `frozen_per_vorgang` | `live` (siehe §7).
- **Notification-Routing** — `notification.routing.mode` = `all_participants` | `priority_only` (siehe §19).
- **Sharing-Default** — `share.default.permission` = `read_only` | `comment` (siehe §25).
- **Action-Confirm-Schwelle** — welche Aktionen brauchen Draft/Confirm-Flow (siehe §13).

### UI

- **Plattform-Settings** im Admin View (§15).
- **Tenant-Settings** im Tenant-Admin-Bereich.
- **Entity-Settings** im Entity-Overlay (§14) als Tab "Einstellungen" — sichtbar nur für berechtigte Rollen.
- **Chat-Session-Settings** als Zahnrad im Chat-Header.

Jede Setting zeigt zusätzlich, **welche Schicht den effektiven Wert liefert** — damit klar ist, ob man hier oder höher überschreiben muss.

### Abgrenzung zu Memory (§6)

- **Memory** = AI-Kontext-Information, fließt in Prompts. ("Wir duzen Kunden.")
- **Settings** = Verhaltens-Konfiguration, fließt in Code-Pfade. ("AI-Änderungen als Draft.")

Beide haben dieselbe Schicht-Reihenfolge (groß → klein), bleiben aber strukturell und mechanisch getrennt.

### Was zu klären ist

- Wie versionieren wir Setting-Änderungen? Vermutlich greift dafür der Change-Log (§26) ohnehin — `Setting` ist auch eine Entität.
- Wer darf was setzen? Vermutlich pro `key` eine Mindest-Rolle deklarieren ("nur Plattform-Admin darf retention setzen", "Tenant-Admin darf Modell wählen").
- Schema-Validierung der `value` — pro `key` ein JSON-Schema in einer zentralen Registry?

---

## 28. Person

**Status:** fehlt als eigene Entität — `User`, `Contact`, `Lead` existieren getrennt; eine generische `Person` als gemeinsame Identitäts-Klammer gibt es nicht.

### Vision
- **`Person`** ist die abstrakte Identitäts-Entität für jede natürliche Person, mit der das System direkt oder indirekt zu tun hat: Mitarbeiter, externe Ansprechpartner, Stakeholder, Quellen-Personen ("der Anwalt, der diesen Vorgang begleitet"), Empfehlende.
- **`User`, `Contact`, `Lead` bleiben semantisch eigenständig** — sie sind keine Sub-Typen von `Person`, sondern getrennte fachliche Konzepte mit jeweils eigenem Bezug zur Plattform:
  - `User` = jemand mit Plattform-Login.
  - `Contact` = qualifizierter externer Ansprechpartner im CRM-Kontext.
  - `Lead` = roher externer Kontakt vor Qualifizierung.
- `Person` ist die **gemeinsame Klammer drüber**: einer Person können optional ein `User`, ein oder mehrere `Contact`-Records und/oder `Lead`-Records zugeordnet sein. Dieselbe Person kann gleichzeitig Mitarbeiter, externer Kunde und Privatkontakt sein, ohne dreimal angelegt zu werden.
- **Freitext-Profil** auf der Person: Beschreibung, Rolle/Expertise, Stil, Tabus, Notizen — von Mensch oder AI gepflegt. Die AI nutzt das, um zu entscheiden, *welche Person* sinnvoll als Antwort-Adressat zu einer Conversation (§38), Frage (§39) oder einem Task eingebunden wird.

### Felder (Skizze)
- Pflicht: Anzeigename, polymorpher Anker (auf jede Entität anhängbar).
- Optional: Mail, Telefon, Sprache, Zeitzone, Foto/Avatar-Ref.
- Profil-Block (Freitext): Rolle/Expertise, Persönlichkeit/Stil, Tabus, allgemeine Notizen.
- Verknüpfungen: optional `user_id`, optional `contact_ids[]`, optional `lead_ids[]`.

### Abgrenzung
- **Person ≠ User**: nicht jede Person hat einen Login, aber jeder User entspricht einer Person.
- **Person ≠ Contact / Lead**: Contact/Lead sind CRM-Rollen-Sichten auf eine Person; eine Person kann mehrere Contacts in verschiedenen Kontexten haben.
- **Person ≠ Team (§30)**: Team ist eine Sammlung von Personen/Users.

### Was zu klären ist
- Auto-Anlage: legt das System eine Person beim ersten Contact/Lead an, oder bleibt Person optional und wird auf Wunsch hochgezogen?
- Konflikt-Auflösung: wie merge ich zwei Personen, die sich später als dieselbe rausstellen — Merge-Aktion + Change-Log-Eintrag (§26)?
- Berechtigungen am Profil: wer darf den Freitext einer Person editieren — sie selbst (wenn User), der Owner-User, Tenant-Admin?

---

## 29. Organisation (Organization)

**Status:** teilweise — `Account` existiert als CRM-spezifisches Konzept, aber keine generische `Organization` quer durchs System.

### Vision
- **`Organization`** ist die abstrakte Klammer für jede juristische oder organisierte Einheit, mit der das System zu tun hat: Kunden-Firmen, eigene Tenant-Firma, Lieferanten, Behörden, Gerichte, Partner, Konkurrenten, NGOs, Vereine.
- Heutiger CRM-`Account` wird zur **Rolle** einer `Organization` — eine Organisation kann gleichzeitig Kunde, Lieferant und Behörde sein, ohne dafür drei Records anzulegen.
- Felder: Anzeigename, Branche, Website, Adress-/Place-Anker (§12), Freitext-Profil, Eigentümer-User, polymorpher Anker.
- Polymorph anhängbar wie alle anderen Entitäten.

### Abgrenzung
- **Organization ≠ Account (CRM)**: Account bleibt als CRM-Sicht bestehen (Pipeline-Bezug, Deal-Verknüpfung) und referenziert eine `Organization`. Mehrere CRM-Rollen pro Organization sind möglich.
- **Organization ≠ Team (§30)**: Team ist eine Untergliederung innerhalb einer Organisation, oft ohne eigene juristische Existenz.
- **Organization ≠ Tenant**: Tenant ist die Plattform-Kunden-Einheit (eigene DB). Eine `Organization` kann der Tenant selbst sein ("wir"), aber auch jede externe Org.

### Was zu klären ist
- Migration: bekommen heutige `Account`-Records automatisch eine `Organization` darunter, oder wird `Account` komplett in `Organization` aufgelöst und die CRM-Spezifika werden Rollen-Tags / Sub-Tabelle?
- Hierarchie zwischen Organisationen (Mutterkonzern → Tochter): über §40 Relationship oder eigener `parent_id`?

---

## 30. Team / Gruppe

**Status:** fehlt komplett.

### Vision
- **`Team`** (oder **`Gruppe`**) ist eine benannte Sammlung von Personen oder Users, die für gemeinsame Arbeit, Zuweisung oder Kommunikation zusammengefasst werden.
- Zwei typische Ausprägungen:
  - **Internes Team** (im Tenant) — z.B. "Vertrieb", "Support", "Geschäftsführung". Mitglieder sind `User`s. Wird als Task-Assignee, Notification-Empfänger, Berechtigungs-Gruppe und Memory-Scope verwendet.
  - **Externe Gruppe** — z.B. eine Projekt-Gruppe quer über mehrere Firmen, eine Lieferanten-Allianz, ein Beirat. Mitglieder sind `Person`s.
- Polymorph anhängbar.
- **Verschachtelbar** (analog Project/Process): Unter-Teams sind möglich.

### Felder (Skizze)
- Pflicht: Anzeigename, Typ (`internal` / `external`), polymorpher Anker.
- Optional: Beschreibung, Organization-Ref (zu welcher Org gehört das Team), parent_team_id.
- Mitglieder: M:N-Brücke zu Person (extern) oder User (intern), mit optionaler Rolle im Team und Lebenszeit.

### Abgrenzung
- **Team ≠ Organization**: Untergliederung, oft ohne eigene juristische Existenz.
- **Team ≠ Rolle** am User: Rolle ist ein Berechtigungs-/Funktion-Tag pro Person/User; Team ist die Sammlung selbst.
- **Team ≠ Conversation-Teilnehmer-Liste (§38)**: Conversation kann ein Team als Teilnehmer haben; das ist Bequemlichkeit, nicht Identität.

### Was zu klären ist
- Berechtigungen: vererbt ein Team Berechtigungen an seine Mitglieder, oder ist es nur eine Bequemlichkeits-Sammlung?
- Memory am Team (§6) — z.B. "das Team Vertrieb duzt Kunden grundsätzlich"; Reihenfolge im Prompt-Kontext zwischen Tenant- und User-Memory?
- Externe Gruppen mit Mitgliedern aus mehreren Orgs — wie modellieren wir Sichtbarkeit?

---

## 31. Auftrag (Order / Commission)

**Status:** fehlt — heute teilweise über `Process.kind` abgebildet, aber ohne eigenständigen Begriff.

### Vision
- **`Auftrag`** ist der **externe Trigger einer Arbeit**: jemand beauftragt uns mit einer Sache. Anders als Vorgang (= unsere Arbeitseinheit) und anders als Projekt (= unsere größere Klammer): Auftrag ist die **Eingangs-Sicht** auf den Anlass.
- Felder: Kurztitel, Auftraggeber (Person und/oder Organization), Auftragsdatum, gewünschte Leistung (Freitext + optional verlinkte Anforderungen §32), Annahme-Status (offen / angenommen / abgelehnt / abgeschlossen), Bearbeitungs-Verknüpfung zu Vorgang(en) / Projekt(en).
- **1:n Bearbeitung**: ein Auftrag kann zu mehreren Vorgängen/Projekten führen (Großauftrag mit Teilprojekten), oder ein einzelner Vorgang/Projekt bearbeitet mehrere Aufträge zusammen.

### Abgrenzung
- **Auftrag ≠ Vorgang**: Auftrag ist der Anlass, Vorgang ist unsere Bearbeitung.
- **Auftrag ≠ Anforderung (§32)**: Anforderung ist *was* geliefert werden soll; Auftrag ist *wer hat beauftragt, wann, unter welchen Bedingungen*.
- **Auftrag ≠ Deal (CRM)**: Deal ist die Verkaufs-Phase davor (Akquise, Pipeline); Auftrag ist nach der Beauftragung.

### Was zu klären ist
- Brauchen wir Auftrags-Untertypen (Werkvertrag / Dienstvertrag / interner Auftrag), oder reicht ein Freitext-Typ + Tag (§22)?
- Verbindung Deal → Auftrag → Vorgang → Rechnung: standardisierte Pipeline mit Übergangs-Aktionen, oder lose Verknüpfung?

---

## 32. Anforderung (Requirement)

**Status:** fehlt komplett.

### Vision
- **`Anforderung`** ist eine **präskriptive Aussage**: "Es muss gelten, dass …". Heute modelliert das System nur *was zu tun ist* (Task) und *was ist* (Document) — nicht *was gelten muss*.
- Anforderungen können an Aufträge, Vorgänge, Projekte, Verträge, Normen hängen.
- Felder: Kurztitel, Beschreibung (Freitext, primär), Quelle (verweist auf §35 `Source` oder §36 `Norm`), Status (entworfen / aktiv / erfüllt / verworfen), Erfüllungs-Kriterium (Freitext, optional Checkliste), Priorität, polymorpher Anker.
- **Tasks operationalisieren Anforderungen**: ein Task kann optional `target_cls=core.requirement` haben und gehört damit explizit zu einer Anforderung. Die AI nutzt das, um zu prüfen, ob alle Anforderungen abgedeckt sind ("3 von 5 Anforderungen haben noch keinen offenen Task").

### Abgrenzung
- **Anforderung ≠ Task**: Task = "tu X", Anforderung = "es muss gelten Y". Ein Y kann mehrere X auslösen.
- **Anforderung ≠ Norm (§36)**: Norm ist allgemeingültig (Gesetz, ISO, AGB); Anforderung ist auf einen konkreten Auftrag/Vorgang heruntergebrochen ("für diesen Auftrag fordern wir … gemäß § 312 BGB").
- **Anforderung ≠ Decision (§37)**: Decision ist eine Festlegung im Verlauf; Anforderung ist eine Vorgabe von außen oder zu Beginn.

### Was zu klären ist
- Versionierung: was passiert mit Tasks, wenn sich eine Anforderung ändert — Snapshot pro Task oder Live-Verlinkung?
- Abnahme-Workflow: wer markiert eine Anforderung als erfüllt, und braucht es eine Gegenzeichnung?
- AI-Extraktion: soll die AI aus Auftragstexten automatisch Anforderungs-Kandidaten extrahieren?

---

## 33. Problem (Issue)

**Status:** fehlt komplett.

### Vision
- **`Problem`** ist ein erfasster **Ist-Abweichungs-Befund**: "Hier stimmt etwas nicht / hier hakt es". Anders als Task (was zu tun ist) und anders als Frage (§39, was offen ist): Problem beschreibt eine **Beobachtung** in der Welt, die behandelt werden sollte.
- Felder: Kurztitel, Beschreibung (Freitext), Schwere (gering / mittel / hoch / kritisch), Status (offen / in Bearbeitung / gelöst / akzeptiert / verworfen), Symptome (Freitext oder verlinkte Events §2), Lösungs-Notiz (Freitext, optional Verweis auf Decision §37), polymorpher Anker.
- **Probleme triggern Arbeit**: aus einem Problem können Tasks, ein eigener Vorgang oder eine Conversation (§38) entstehen.

### Abgrenzung
- **Problem ≠ Task**: Problem beschreibt einen Zustand, Task ist die Handlung dagegen.
- **Problem ≠ Reklamation**: Reklamation ist ein Sonderfall (extern gemeldetes Problem mit Vertragsbezug); Problem ist allgemeiner und intern wie extern.
- **Problem ≠ Frage (§39)**: Frage = "ich weiß etwas nicht und brauche eine Antwort"; Problem = "ich beobachte einen Missstand".

### Was zu klären ist
- Sollte es eine eigene "Lösung"-Sub-Entität geben, oder reicht es, das gelöste Problem mit verlinktem Decision (§37) abzuschließen?
- Eskalation: wie wird aus einem Problem ein Vorgang — automatisch via Schwere-Schwelle / per Aktion?

---

## 34. Ressource (Resource / Asset)

**Status:** fehlt komplett.

### Vision
- **`Ressource`** ist ein **gegenständliches oder kapazitäres Etwas**, das gebucht, zugewiesen, verbraucht oder verwaltet wird: Maschinen, Werkzeuge, Fahrzeuge, Räume, Lizenzen, virtuelle Slots ("Telefonleitung 1"), Roh-/Verbrauchsstoffe, Server, Software-Accounts.
- Felder: Anzeigename, Typ (Freitext + optional Tag), Verfügbarkeits-Status (verfügbar / gebucht / wartung / außer Betrieb), Standort (verweist auf `Place` §12), Eigentümer/Verantwortlicher (Person/Organization), Beschreibung, polymorpher Anker.
- Verknüpfung zu **Appointments (§20)** für Buchungen ("Raum X ist am 12.3. für Termin Y belegt"), zu **Tasks** für Zuweisung, zu **Vorgängen** für Einsatz-Tracking.

### Abgrenzung
- **Ressource ≠ Document**: Dokument ist Inhalt, Ressource ist Gegenstand.
- **Ressource ≠ Person/Team**: auch wenn Personen im Planungs-Sinn "Ressourcen" sind — Person bleibt eigene Entität (§28); Ressource ist für Nicht-Menschliches.
- **Ressource ≠ Place (§12)**: Place ist ein Ort (auch ohne Bewegung/Verbrauch); Ressource ist etwas, das verfügbar oder belegt sein kann.

### Was zu klären ist
- Buchungs-Mechanik: Doppelbuchungs-Schutz im Code (Constraint) oder als Workflow-Regel?
- Inventar-Mengen: brauchen wir Stückzahl-Felder für Verbrauchsstoffe, oder bleibt das im Freitext bis ein eigenes Inventar-MCP kommt?
- Wartungs-Trigger: Ressource → AI-Reminder (§23) für regelmäßige Checks?

---

## 35. Quelle (Source)

**Status:** fehlt komplett. **Hohe Priorität** (Citation-Maschinerie für jede AI-Aussage).

### Vision
- **`Quelle`** ist eine **Referenz auf eine externe Wissens-Wurzel**, von der Inhalte/Aussagen abgeleitet wurden: URL, Buch, Gesetz/Norm-Verweis, gesprächs-Mitschnitt, Auskunfts-Person, internes Vor-Dokument, KI-Suchergebnis-Snapshot.
- Anders als `Document` (eigenständiger Inhalt unter unserer Kontrolle): Quelle ist oft **nicht in unserem Besitz** — wir referenzieren sie und halten eine **AI-erzeugte Zusammenfassung / Auszüge / optional Snapshot** vor.
- Felder: Kurztitel, Art (`url` / `buch` / `norm` / `person` / `datei` / `sonstiges`), Originaler Verweis (URL, ISBN, Aktenzeichen, Person-Ref), Zugriffs-Datum, AI-Zusammenfassung (Freitext), gehosteter Snapshot (optional `Attachment`-Verweis), Vertrauenswürdigkeit (gering / mittel / hoch), polymorpher Anker.

### Citation-Maschinerie
- Die AI **legt automatisch Quellen-Einträge an**, wenn sie aus extern recherchierten Informationen zitiert (z.B. Web-Researcher-Sub-Agent §8). Antworten im Chat können "Quellen"-Footnotes haben, die auf diese Einträge zeigen.
- Beim Erstellen einer Anforderung (§32), einer Norm-Referenz (§36) oder einer Decision (§37) verlangt die UI auf Wunsch eine verknüpfte Quelle — "warum gilt das, woher weißt du das".

### Abgrenzung
- **Quelle ≠ Document**: Document = eigener Inhalt unter unserer Kontrolle; Quelle = Verweis auf fremden Inhalt.
- **Quelle ≠ Norm (§36)**: Norm ist präskriptives Wissen mit eigener Struktur (Paragraphen); eine Norm *kann* eine Quelle haben (das tatsächliche Gesetzes-Dokument), bleibt aber eine eigenständige Anforderungs-Entität.
- **Quelle ≠ ExternalEvent (§20)**: ExternalEvent = Audit-Spur unserer Aktion an die Außenwelt; Quelle = Wissens-Wurzel, die in unsere Welt reinfließt.

### Was zu klären ist
- Wie weit holen wir den Inhalt rein — kompletter Snapshot vs. nur AI-Summary vs. nur Link? Wahrscheinlich konfigurierbar pro Quelle/Tenant.
- Verfall: was tun, wenn eine Web-Quelle weg ist (404) — reicht der Snapshot, oder als "stale" markieren?
- Verhältnis zum Semantic-Index: Quellen-Auszüge gehören in den Index, der Original-Verweis nicht.

---

## 36. Norm (Law / Regel / Standard)

**Status:** fehlt komplett.

### Vision
- **`Norm`** ist **präskriptives, oft öffentlich gültiges Wissen mit hierarchischer Struktur**: Gesetze, Verordnungen, AGB, ISO-Normen, DIN-Standards, interne Policies, branchenspezifische Regelwerke.
- **Nestbar / verschachtelt**: Norm → Untergliederung (Buch / Teil / Kapitel / Paragraph / Absatz / Satz). Tiefe ist beliebig, Standard-Drill ist ein Selbst-Verweis (`parent_id`).
- Felder: Titel, Kurzbezeichnung ("§ 433 BGB"), Volltext oder Auszug, Geltungsbereich (Freitext, optional Tag), Inkrafttreten, Ablöse-Datum, Sanktion bei Verstoß (Freitext), Quelle-Ref (§35), polymorpher Anker.
- **Die AI nutzt Normen** als Wissens-Schicht: bei einem Vorgang vom Typ X kann sie automatisch passende Normen vorschlagen ("dieser Vorgang berührt § 312 BGB").
- **Polymorph anhängbar** — eine Norm wird an einen Vorgang/Auftrag/Anforderung gehängt, wenn sie relevant ist.

### Abgrenzung
- **Norm ≠ Anforderung (§32)**: Norm ist generell ("so muss jeder Werkvertrag aussehen"); Anforderung ist konkret heruntergebrochen ("dieser Werkvertrag mit Kunde Y muss …").
- **Norm ≠ Quelle (§35)**: Norm ist *präskriptiv* und eigenständig in unserem Modell; Quelle ist *deskriptiv* und nur Verweis. Eine Norm kann eine Quelle haben (das Original-Gesetz).
- **Norm ≠ Workflow (§7)**: Workflow beschreibt, wie wir bei uns vorgehen; Norm beschreibt, was von außen vorgegeben ist.

### Was zu klären ist
- Versionierung: wenn ein Gesetz novelliert wird — neue Norm-Entität mit `replaces`-Verweis (§40 Relationship) oder Version-Snapshot der alten?
- Suche: Norm-Volltexte können sehr lang werden — Stückung pro Paragraph für den Semantic-Index?
- Branchenspezifische Default-Normsets pro Tenant — kommt mit MCP-Domain-Plug-ins (§21)?

---

## 37. Entscheidung (Decision)

**Status:** fehlt komplett.

### Vision
- **`Decision`** ist eine **kuratierte Aufzeichnung einer getroffenen Entscheidung**: was wurde beschlossen, von wem, wann, auf welcher Grundlage, gegen welche Alternativen.
- Felder: Kurztitel, Beschreibung (Freitext), Entscheidende(r) (Person/Team), Datum, Optionen (Freitext-Liste, optional strukturiert), Begründung, erwartete Wirkung (Freitext + verlinkte Tasks/Anforderungen), Status (vorgeschlagen / beschlossen / revidiert), polymorpher Anker.
- Verknüpfung zu Quelle (§35) für die Grundlage, zu Anforderung (§32) für die Wirkung, zu Conversation (§38) für die Entstehungs-Diskussion.

### Abgrenzung
- **Decision ≠ Comment**: Comment ist Diskussions-Beitrag im Verlauf; Decision ist das Ergebnis am Ende einer Diskussion.
- **Decision ≠ Task-Status**: ein Task abzuhaken ist eine Mikro-Entscheidung; Decision ist die kuratierte, erinnerungswürdige Festlegung.
- **Decision ≠ EntityChange (§26)**: Change-Log ist die maschinelle Feld-Diff-Buchhaltung; Decision ist die menschen-/AI-formulierte Bedeutung dahinter.

### Was zu klären ist
- AI-Vorschlag: soll die AI aus Conversations (§38) und Comments automatisch Decision-Kandidaten extrahieren ("hier wurde anscheinend etwas beschlossen, soll ich das als Decision festhalten")?
- Reversibilität: wenn eine Decision später revidiert wird — neue Decision mit Verweis (Relationship `revidiert`) auf die alte, oder Status-Wechsel?

---

## 38. Konversation (Conversation)

**Status:** fehlt — `Comment` existiert als Einzel-Eintrag, aber kein Diskurs-Container, der mehrere Menschen und optional die AI als Teilnehmer kennt.

### Vision
- **`Conversation`** ist ein **menschen-zentrierter Diskurs-Faden**, der polymorph an einer beliebigen Entität hängt — die "Kommentar-Spalte an alles".
- Mehrere **Personen** (§28) sind Teilnehmer; die **AI kann mitreden**, aber der Faden gehört konzeptionell den Menschen.
- Felder: Titel (optional), Anker (`target_cls`/`target_id`), Teilnehmer-Liste (Person-Refs, optional Team-Refs), Status (offen / archiviert), Sichtbarkeit (privat / Team / öffentlich), polymorpher Anker.
- **Beiträge** sind `Comment`-Einträge (existiert): `Comment` bekommt einen optionalen `conversation_id`-Anker — ohne Conversation bleibt Comment der "lose Kommentar an etwas".

### AI-Rolle
- Die AI kann zu jeder Conversation **vorschlagen, welche Personen sinnvoll einzubinden wären** — dafür liest sie die Profil-Freitexte der Personen (§28). Beispiel: "Frage zu Maschinenbau-Norm — soll ich Hans (Profil: 'Maschinenbau-Ingenieur, 20 Jahre Erfahrung') hinzufügen?"
- Die AI kann selbst Beiträge schreiben, mit klarer Markierung als AI-Beitrag (analog §22 Tag-Setter `human`/`ai`).
- Die AI kann eine Conversation zusammenfassen und einen Decision-Vorschlag (§37) daraus ableiten.

### Abgrenzung
- **Conversation ≠ AiChat (§10)**: AiChat ist AI-zentriert (Mensch ↔ Agent oder Agent ↔ Sub-Agent); Conversation ist Mensch ↔ Mensch, AI optional als Teilnehmer.
- **Conversation ≠ Comment**: Comment ist der einzelne Beitrag; Conversation ist der gebündelte Faden.
- **Conversation ≠ Interaction (CRM)**: Interaction ist ein extern stattgefundener Touchpoint (Anruf, Mail); Conversation ist die Diskussion über die Plattform.

### Was zu klären ist
- @-Mentions: Notification (§19) automatisch?
- AI-Default-Verhalten: in einer Conversation standardmäßig stumm und nur auf Aufruf antworten, oder darf sie sich von selbst melden? → wahrscheinlich eine Setting (§27).
- Verhältnis zu Sub-Chats (§10): wenn die AI in einer Conversation länger arbeitet, spawnt sie einen AiChat — wie wird der zurückgekoppelt?

---

## 39. Frage (Question)

**Status:** fehlt komplett.

### Vision
- **`Question`** ist eine **explizit erfasste, noch offene Frage**: jemand weiß etwas nicht oder braucht eine Bestätigung, und das wird festgehalten — statt in einer Conversation zu versickern.
- Felder: Frage-Text, gestellt von (Person), gerichtet an (Person/Team oder die AI), Status (offen / beantwortet / verworfen), Antwort (Freitext, optional Verweis auf Decision §37 oder Source §35), polymorpher Anker.
- **Polymorph anhängbar** — jede Entität kann offene Fragen tragen, die die AI im jeweiligen Kontext mit-präsentieren kann ("zu diesem Vorgang gibt es 2 offene Fragen").
- Die AI kann Fragen aus Conversations/Notes/Mails extrahieren ("hier hat jemand gefragt, soll ich das als offene Frage festhalten?") und Antworten vorschlagen.

### Abgrenzung
- **Question ≠ Task**: Task ist Tu-Auftrag; Question ist Wissens-Lücke. Aus einer Frage *kann* eine Task entstehen ("Frag den Anwalt").
- **Question ≠ Problem (§33)**: Problem = beobachteter Ist-Missstand; Question = fehlende Information.
- **Question ≠ Decision (§37)**: Question ist das Davor; Decision ist das Danach.

### Was zu klären ist
- Soll die AI eigene Wissens-Lücken automatisch als `Question` anlegen statt zu spekulieren ("Ich weiß nicht, soll ich das als offene Frage an X stellen?")?
- Aging: alte unbeantwortete Fragen — automatische Eskalation via AI-Reminder (§23), oder bleiben sie still liegen?

---

## 40. Relationship

**Status:** fehlt als first-class — heute implizit über polymorphe Anker auf einzelnen Entitäten.

### Vision
- **`Relationship`** ist eine **getypte, mit Lebenszeit versehene Beziehung zwischen zwei Entitäten**. Beispiele: "Person A ist Vorgesetzte von Person B (seit 2024-01-01)", "Organization X ist Tochter von Y", "Vorgang A ist Folge-Vorgang von B", "Document A ersetzt Document B", "Norm A wurde durch Norm B abgelöst".
- Felder: Quelle (`from_cls`/`from_id`), Ziel (`to_cls`/`to_id`), Beziehungs-Typ (Freitext oder Tag-Ref, z.B. `vorgesetzt`, `tochter_von`, `ersetzt`, `ist_quelle_von`, `folge_von`), Beginn, Ende (optional), Beschreibung (Freitext), polymorpher Eigentümer-Anker.
- **Symmetrie**: per Default gerichtet; symmetrische Beziehungen werden über zwei Einträge oder ein Symmetrie-Flag modelliert.

### Wofür gut, jetzt mit AI
- AI kann **Beziehungs-Netze** lesen, um Kontext herzustellen ("Person A ist Vorgesetzte von Person B → frag erst A, bevor du B störst").
- AI kann **Beziehungen vorschlagen**, wenn sie aus Text Patterns erkennt ("hier wird mehrfach gesagt, dass X von Y abhängt — Relationship anlegen?").
- **Org-Charts, Genealogien, Vorgangs-Ketten, Quellen-Verkettungen, Norm-Ablöse-Ketten** werden alle über denselben Mechanismus abgebildet, statt pro Domäne eigene M:N-Tabellen.

### Abgrenzung
- **Relationship ≠ polymorpher Anker** (`target_cls`/`target_id`): der Anker ist eine Besitz-/Zuordnungs-Hierarchie ("Note gehört zu Vorgang"). Relationship ist eine fachliche Beziehung mit eigener Lebenszeit und Typ.
- **Relationship ≠ Tag (§22)**: Tag ist Klassifizierung einer Entität; Relationship ist eine konkrete Verbindung zwischen zwei Records.
- **Relationship ≠ ChatArtifact (§24)**: ChatArtifact ist die Mappe-pro-Chat, technisches Tracking; Relationship ist fachlich.

### Was zu klären ist
- Wie verhindern wir Sprawl (jede Kleinigkeit als Relationship)? Wahrscheinlich Allow-Liste an erlaubten Beziehungs-Typen pro Tenant, AI-Vorschläge laufen über Approval.
- Cycle-Detection bei hierarchischen Typen (Vorgesetzte → Vorgesetzte → … → erste Person).
- Visualisierung — wo sieht der Nutzer ein Beziehungs-Netz: Sidebar-Tab pro Entität, Explorer-View, oder eigenes Graph-Overlay (§11)?

---

## 41. Wert / Position / Transaktion (Roadmap)

**Status:** bewusst aufgeschoben — kommt mit einem eigenen Buchhaltungs-/Faktura-MCP (§21).

### Vision
Eine **quantitative Schicht** für Geld-, Material- und Verantwortungs-Flüsse:
- **Position / Line-Item** — atomare Reihe einer Aufstellung (Rechnungs-Position, Inventar-Reihe, Stückliste, Angebots-Position).
- **Transaktion** — gerichtete Wert-Bewegung (Buchung, Lager-Bewegung, Verantwortungs-Übergabe).
- **Wert-Aggregate** — Saldo, Buchungs-Konten, Bilanz-Sichten.

### Warum nicht jetzt
Diese Schicht **kommt mit einem eigenen Buchhaltungs- / Faktura-MCP** (§21) und wird im Kern bewusst nicht vorgegriffen, weil die Domänen-Spezifika (Steuer, Konten-Rahmen, Rechnungsstellung, Buchungslogik) zu reichhaltig sind, um abstrakt sinnvoll modelliert zu werden — das ist genau ein Fall, wo ein Domain-MCP die richtigen Spalten und Mechaniken einbringt.

### Bezug zu anderen Konzepten
- **Auftrag (§31)** und **Anforderung (§32)** sind die qualitativen Pendants — sie beschreiben *was*; diese Schicht beschreibt *zu welchem Wert*.
- **Deal (CRM)** ist eine frühe quantitative Annäherung; ein Buchhaltungs-MCP würde Deals zu Positionen/Transaktionen weiterführen.
- **Ressource (§34)** kann mit Verbrauchs-Transaktionen verknüpft sein (Lager-Abbuchung).

---

## Querschnitts-Themen

### Semantische Indexierung
**Status:** vorhanden — `SemanticFassade` + `SemanticSnippet` + pgvector (1536 Dim).
- Jede neue Entität (Vorgang, Workflow, Memory, Event, Address, Place) muss in das Semantic-Sync eingebunden werden.

### Telemetrie / Event-Streaming
**Status:** vorhanden — `EventEmitter` und SSE-Stream (`lib/events.py`).

Das Event-Vokabular wächst um zwei Familien:

**a) Sub-Agent-Lifecycle** (siehe §8) — pro Sub-Chat-Spawn:
- `sub_agent_started` — `{role, parent_trace_uid, sub_trace_uid, sub_chat_id, task_brief}`
- `sub_agent_progress` — `{role, sub_trace_uid, status_text}`
- `sub_agent_completed` — `{role, sub_trace_uid, summary, outcome_preview, duration_ms, status}`

Diese Events sind die Grundlage für die Chat-UI-Anzeige ("Archivar sucht …") und den Live-Tab im Debug-View (§16).

**b) Entity-Change** (siehe §26) — pro persistierter Feld-Änderung:
- `entity_changed` — `{change_id, target_cls, target_id, change_type, actor_type, summary}` (volatil im Stream; die kanonische Speicherung ist `logging_db.entity_change`, der Stream-Event ist nur der Push-Hook für Live-Updates).

So weiß die UI sofort, wenn z.B. ein Vorgang im offenen Overlay durch einen anderen User oder einen AI-Agenten verändert wurde, und kann den Verlaufs-Tab live nachziehen.

Wichtig: `logging_db.event` (Telemetrie pro Chat-Runde) und `logging_db.entity_change` (Audit pro Feld-Änderung) bleiben **getrennte Tabellen** — die Event-Stream-Schicht ist nur der gemeinsame Live-Push-Kanal.

### Authentifizierung / Berechtigung
**Status:** vorhanden, dünn — Session-Cookie, einfache Rollen.
- Granulare Rechte pro Aktion / pro Vorgang fehlt noch.

**Rollen im Tenant:**
- **Tenant-Administrator** — direkter Kunde, voller fachlicher Zugriff im Tenant, verwaltet Mitarbeiter.
- **Tenant-Mitarbeiter** — vom Tenant-Admin angelegt, fachlicher Zugriff je nach Rolle.
- **Tenant-Supporter** — unser eigener Support-Account, der **als Tenant-Nutzer** eingebunden ist, um beim Tenant reingucken und Probleme diagnostizieren zu können. Sieht zusätzlich zu den fachlichen Entitäten auch interne (`SemanticSnippet`, `AiToolCall`, `AiMessage`, …); siehe Explorer-Sichtbarkeit in §18.

**Rollen oberhalb des Tenants:**
- **Plattform-Admin** — Betreiber-Sicht (§15), arbeitet auf `admin_db` und kann read-only in jeden Tenant gucken.

---

## Geklärte Punkte (Runde 1)

- ✅ **Projekt vs. Vorgang** — getrennt. Projekt = größere Klammer, Vorgang = kleinere, anlassgetriebene Arbeitseinheit. Vorgang kann zu Projekt gehören. (§1)
- ✅ **Memory-Reihenfolge** — vom Großen ins Kleine: Tenant → User → Entity. (§6)
- ✅ **Workflow-Struktur** — Freitext-Pflicht, Struktur (Phasen/Schritte/Übergänge) optional. (§7)

## Geklärte Punkte (Runde 2)

- ✅ **Explorer als zweite UI-Hauptachse** — universeller Entity-Navigator mit speicherbaren Views; bewusst nicht "Wiki" (würde mit `Document` kollidieren), Arbeitstitel "Explorer". (§18)
- ✅ **Drei View-Typen** — dynamisch (Query), kuratiert (Baum), Hybrid (Mix). V1 ohne Hybrid. (§18)
- ✅ **View als Entität** — `View` ist eine reguläre Tenant-Entität, taucht selbst im Universe auf, ist semantisch indexierbar. (§18)
- ✅ **Rekursion = Link, keine Auto-Expansion** — eine View, die eine andere View enthält, lädt den Sub-Baum erst auf Klick. (§18)
- ✅ **AiChat bekommt polymorphen Anker** — `target_cls` / `target_id` analog zu `Document`. Voraussetzung für Chat-View-Kopplung und sauberere Sub-Chats. (§10, §18)
- ✅ **View-Sichtbarkeit ist rollenabhängig** — Tenant-Admin/Mitarbeiter sehen fachliche Entitäten; Tenant-Supporter zusätzlich interne. Pro `@register_entity` ein `explorer_scope`-Marker. (§18, Auth-Querschnitt)
- ✅ **View-Spec ist tenant-geteilt, Evaluation pro Aufrufer** — die Spec lebt einmal, die Ergebnis-Reihen werden pro Caller-Permission gefiltert. (§18)
- ✅ **View-Spec-Format = strikt typisiertes JSON** — deterministisch evaluierbar und AI-generierbar (Tool-Call mit Schema). (§18)
- ✅ **Drei Action-Scopes im Explorer** — Entity-Action / View-Action / Node-Action. (§18)
- ✅ **Tenant-Supporter als Rolle** — eigener Tenant-Account, den wir nutzen, um beim Tenant Support zu leisten. (Auth-Querschnitt)

## Geklärte Punkte (Runde 4)

- ✅ **Change-Log pro Entität** als generischer Audit-Trail — eigene `EntityChange`-Tabelle in `logging_db`, append-only, automatisch über `BaseMixin`-Hooks befüllt. (§26)
- ✅ **Granularität: 1 Eintrag pro logischem Vorgang** — Feld-Diffs als JSONB-Liste, nicht je ein Eintrag pro Feld. (§26)
- ✅ **`trace_uid` als Brücke Telemetrie ↔ Fachlichkeit** — fachliche Events (§2) und Change-Log-Einträge (§26) tragen die Trace-UID, in der sie entstanden sind; vom Vorgangs-Verlauf in zwei Klicks beim auslösenden LLM-Prompt. (§2, §26, §16)
- ✅ **Debug-View als eigene, information-dichte UI** — drei Drilldown-Achsen (Trace / Entität / Agent), Devtools-mäßiger Anspruch, sichtbar nur für Tenant-Supporter und Plattform-Admin. (§16)
- ✅ **Admin View und Debug View bleiben getrennt** — Admin = Plattform-Betrieb (Mutation), Debug = Diagnose (read-mostly). (§15, §16)
- ✅ **MCPs deklarieren `kind`** — `tool` / `sub_agent` / `mixed`, im Manifest. Konsequenz: Lifecycle-Events nur für Sub-Agent-MCPs, getrennte Listung im Debug-View, separate Quota-Tarifierung. (§21)
- ✅ **Sub-Agent-Lifecycle als Event-Typen** — `sub_agent_started`/`progress`/`completed` mit Result-Contract-Bezug; Grundlage für Live-Status im Chat und Debug-View. (§8, Querschnitt Telemetrie)
- ✅ **Settings-Hierarchie als eigenes Konzept** — vier Schichten Plattform / Tenant / Entity / Chat-Session, gleiche Reihenfolge wie Memory, ein zentraler Resolver. (§27)
- ✅ **AI-Änderungs-Modus ist eine Setting**, nicht hardcoded — `direct` / `draft` / `draft_for_critical_fields`, überall in der Settings-Hierarchie überschreibbar. (§26, §27)
- ✅ **Change-Log → Event-Generator pro Entity-Typ konfigurierbar** — z.B. jedes `status`-Update am Vorgang erzeugt automatisch ein fachliches Statuswechsel-Event in der Timeline. (§26)

## Geklärte Punkte (Runde 3)

- ✅ **Notifications laufen über den Explorer, keine Inbox-UI** — Notification ist eine Entität mit Read-State; konsumiert über Default-View "ungelesen". (§19)
- ✅ **Externe Welten = eigene Entitäten** — Mail, Appointment, ExternalEvent statt ad-hoc-Strings. Anbindung über MCPs. (§20)
- ✅ **`ExternalEvent` als Audit-Spur nach aussen** — eigene Entität für alles, was rausgeschickt oder bei Drittsystemen geändert wurde. (§20)
- ✅ **MCPs sind die domain-Plug-in-Schicht** — Hauptanwendung bleibt domänen-agnostisch. (§21)
- ✅ **MCPs haben Manifeste** — Self-Description mit Tools, verwalteten Entitäten, Abhängigkeiten, Berechtigungen, UI-Erweiterungen. (§21)
- ✅ **MCPs können selbst Sub-Agents administrieren** — Abteilungsleiter-Muster, nicht nur Tool-Provider. (§21)
- ✅ **MCPs liefern eigene Edit-UI** — sandboxed iFrame/Micro-Frontend im normalen Overlay-Stack; Core muss nichts über die Domain wissen. (§21, §14)
- ✅ **Tags markieren ihren Setter** — `human` vs. `ai` pro `TagAssignment`, in UI sichtbar/filterbar. (§22)
- ✅ **Reminders adressieren Mensch ODER AI-Worker** — AI-Reminder triggern Cron-artig einen Agenten, nicht nur eine Notification. (§23)
- ✅ **ChatArtifact ist die Mappe-pro-Chat-Mechanik** — orthogonal zum 1:1-Chat-Anker; M:N mit kategorisierter Relation. (§24)
- ✅ **Sharing-Links: Team-Shared + Public-Shared** — eigene `Share`-Entität mit Token/Permission/Ablauf. (§25)
- ✅ **Sub-Agent-Result-Contract** — fester Vertrag (`summary` + `outcome` + `artifacts` + optional `confidence`/`open_questions`), statt voller Sub-Verlauf oder freier String. (§10)
- ✅ **Sicherheit / AI-Guardrails bewusst vertagt** — kommt erst, wenn echte Kunden im System sind.
- ✅ **Globale Suche braucht keine eigene UI** — geht über den Explorer (§18) mit. Kein Quick-Open als Extra-Konzept.
- ✅ **Onboarding / Abrechnung / Templates / AI-Chat-Memory** bewusst vertagt — Kern-Funktionalitäten zuerst.

## Offene Diskussionspunkte (für die nächste Runde)

1. **Memory-Größen-Strategie** — wie verhindern wir Token-Sprawl?
2. **Aktions-UI** — wo werden vorgeschlagene Aktionen angezeigt (im Chat-Verlauf, in Sidebar, beides)?
3. **Worker-Rollen-Sichtbarkeit** — wie zeigt der Hauptmanager dem Nutzer, welcher Sub-Agent arbeitet?
4. **Visualisierungs-Pipeline** — eigener Agent oder Tool, das überall nutzbar ist?
5. **Workflow-Versionierung** — eingefrorene Version pro Vorgang oder immer live?
6. **Code-Name für Vorgang** — `Process`, `Case`, `Vorgang` direkt?
7. **Explorer: endgültiger Name** — `Explorer`, `Büro`, `Hub`, `Workspace`?
8. **Explorer: View-Spec JSON-Schema** — konkretes Schema beim Implementieren festzulegen.
9. **Explorer: gemischte Entity-Typen in einer View** — gemeinsame Spalten oder pro Typ eigene Darstellung?
10. **Explorer: AI-vorgeschlagene Views** — wann/wo proaktiv ("Übersicht über ähnliche Vorgänge")?
11. **Sub-Chat-UI: Live-Tail vs. Live-Status vs. nur Ergebnis-Karte?** (§10)
12. **Sub-Chat-Tiefe: hartes Limit vs. Kosten-Warnung?** (§10)
13. **Notification-Routing** — alle Beteiligten oder Prio-Empfänger? AI-Spam-Schutz? (§19)
14. **Mail V1 — IMAP/SMTP direkt oder Provider-OAuth?** (§20)
15. **MCP-Manifest-Format und UI-Erweiterungs-Protokoll** — JSON-Schema-Datei vs. Endpunkt; iFrame+postMessage vs. WebComponent? (§21)
16. **Tag-Hierarchie vs. flach?** Lebenszyklus von Tag-Löschungen? (§22)
17. **AI-Reminder-Quota pro Tenant** — wie verhindern wir unkontrollierte Cron-Explosion? (§23)
18. **Sharing: externe Kommentator-Identität** — Pseudo-Account, nur Name+Mail, oder Magic-Link-Login? (§25)
19. **Change-Log: Tiefe der Feld-Diffs bei großen Text-Feldern** — voller alter+neuer Text oder nur Diff-Snippet? Bulk-Operationen: ein Eintrag pro Reihe oder gebündelt? (§26)
20. **Settings-Schema-Validierung** — pro `key` ein JSON-Schema in zentraler Registry? Wer darf welche Settings setzen (Mindest-Rolle pro Key)? (§27)
21. **Change-Log im Semantic-Index** — soll `summary` semantisch durchsuchbar sein ("wann hat AI den Status geändert")? (§26, Querschnitt Semantik)

---

## Roadmap-Anker (kommt später)

Hier später die priorisierte Feature-Liste, die wir aus diesem Dokument ableiten.
Format: `[#] Feature — Konzept-Ref — Begründung — Aufwandsindikation`.

_(noch leer)_
