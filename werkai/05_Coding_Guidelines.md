# 💻 Coding Guidelines & Anti-Slop Direktiven

Dieses Dokument enthält verbindliche Vorschriften für die Qualität, Dichte und Struktur des geschriebenen Codes. KIs und Coder müssen sich bedingungslos an diese Vorgaben halten.

## 1. Die Anti-Slop Direktive
„AI Slop“ (funktionaler, aber aufgeblähter, redundanter und schwer lesbarer Code) ist im Projekt verboten. 
- **Regel**: *Schreibe so wenig Code wie möglich bei maximaler Funktionalität.*
- Jede Zeile Code ist eine potenzielle Fehlerquelle und erhöht den Wartungsaufwand.

## 2. Der Code-Dichte-Workflow (für KIs)
1. **Logik entwerfen**: Funktionale Anforderung mental skizzieren.
2. **Re-use Check**: Durchsuche die bestehende Codebase (z.B. `/lib/`) nach bereits vorhandenen Hilfsfunktionen (z.B. Logging, DB-Verbindungen). Erfinde das Rad **nicht** neu!
3. **Schreiben**: Implementiere den Code.
4. **Minimieren (Self-Critique)**: Analysiere den geschriebenen Code selbstständig:
   - Lassen sich verschachtelte `if`-Abfragen durch *Early Returns* abkürzen?
   - Können Standard-Sprachfeatures (z.B. Python List Comprehensions, Generatoren, dict-Merges) den Code verkürzen?
   - Können doppelte Validierungen oder überflüssige Imports entfernt werden?
5. **Kürzen**: Reduziere die Datei auf das absolute Minimum, ohne die Lesbarkeit für Menschen zu beeinträchtigen.

## 3. Best Practices (Python / FastAPI)
- **Early Returns**: Vermeide tiefe Einrückungen.
  ```python
  # Schlecht:
  if user:
      if user.is_active:
          return process(user)
  
  # Gut:
  if not user or not user.is_active:
      return None
  return process(user)
  ```
- **Zentrales Logging**: Verwende ausschließlich das in `/lib/logging.py` konfigurierte Logging. Keine rohen `print()` Statements.
- **Keine leeren try-except Blöcke**: Fange spezifische Exceptions ab und logge sie mit `log.exception()`.
- **Kommentare**: Kommentiere das *Warum*, niemals das *Was*. KIs neigen dazu, jede Zeile redundant zu kommentieren (z.B. `# returns the status` über `return status` ist verboten).

## 4. Automatisiertes Quality Gate (Minification Check)

Jede Modifikation an Python-Dateien wird automatisch durch ein AST-basiertes Skript ([minify_check.py](file:///c:/Users/Theo/Downloads/wai-main/scripts/minify_check.py)) validiert. 

### Erzwungene Dichte-Metriken:
- **Einrückungstiefe (Nesting)**: Verzweigungen (`if`, `for`, `while`, `try`) dürfen **maximal 2 Ebenen** tief verschachtelt sein. Nutze Early Returns oder Early Continues.
- **Funktionslänge**: Funktionen dürfen **maximal 25 Zeilen** lang sein. Teile größere Logik in kompakte Hilfsfunktionen auf.
- **Redundante Try-Excepts**: Try-except-Blöcke, die Fehler lediglich loggen und via `raise` unverändert weiterwerfen, sind verboten.
- **Loop-Kompression**: Einfache `for`-Schleifen mit `.append()` müssen als kompakte List/Dict Comprehensions geschrieben werden.

### Manuelle & Automatische Ausführung:
Vor jeder Finalisierung einer Code-Änderung muss im Terminal ausgeführt werden:
```bash
python scripts/minify_check.py <dateipfad>
```
Ergebnisse werden protokolliert. Verstöße verhindern die Akzeptanz des Codes im Repository.
