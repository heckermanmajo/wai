# 🔌 MCP-Schnittstellen-Spezifikation (Model Context Protocol)

Dieses Dokument regelt, wie die Model Context Protocol (MCP) Server und Tools für unsere finale Agenten-Plattform entworfen und angebunden werden.

## 1. Trennung von Agenten und Tools
- **Agents** = Entscheidungsträger. Sie verwalten Unsicherheit, interpretieren Absichten (Intents), planen Schritte und entscheiden über Aktionen. Sie laufen primär auf LLMs.
- **Tools / MCP-Server** = Deterministische Ausführende. Sie liefern klare Schnittstellen (APIs), schreiben in Datenbanken, rufen externe Endpunkte auf oder manipulieren Dateien. Sie tun genau das, was ihnen aufgetragen wird, und geben strukturierte Ergebnisse zurück.

## 2. Struktur unserer MCP-Server
Unsere MCP-Server werden standardmäßig in **Python** (unter Verwendung von Bibliotheken wie `FastMCP`) oder **TypeScript** implementiert.

### 2.1 WhatsApp Ingestion MCP (Beispiel-Konzept)
- **Beschreibung**: Stellt Schnittstellen zur WhatsApp Business API (360dialog/Twilio) bereit.
- **Tools**:
  - `send_whatsapp_message(to: string, body: string)`: Sendet einen Text oder ein Template an einen Kunden.
  - `get_whatsapp_media(media_id: string)`: Holt ein Foto oder eine Sprachnachricht von der Baustelle ab.
  - `parse_baustellen_audio(audio_data: bytes)`: Übergibt Audiodaten an Whisper zur Transkription.

### 2.2 E-Mail Parsing MCP
- **Beschreibung**: Schnittstelle zum IMAP-Eingang und SMTP-Ausgang.
- **Tools**:
  - `list_unread_emails()`: Holt ungeladene E-Mails ab.
  - `create_email_draft(to: string, subject: string, body: string)`: Bereitet einen Antwort-Entwurf im Postfach vor.

### 2.3 Baserow / Airtable Sync MCP
- **Beschreibung**: Bindet das NoCode-Frontend/CRM der Kunden an.
- **Tools**:
  - `create_lead_entry(candidate_data: dict)`: Legt eine Zeile in Baserow an.
  - `update_appointment_status(record_id: string, status: string)`: Setzt Freigabestatus.

## 3. Konventionen für die Tool-Erstellung
- Jedes Tool muss eine präzise Beschreibung (`description`) und exakt definierte Pydantic- oder JSON-Schema-Parameter besitzen, damit die Agenten sie fehlerfrei aufrufen können.
- Fehlerhafte API-Aufrufe müssen sauber abgefangen und als Fehler-String an das aufrufende Modell zurückgegeben werden, anstatt abzustürzen.

## 4. Entwicklungs- und Hilfs-MCP-Server (Dev-Setup)

Für den Software-Entwicklungszyklus in der IDE (Roo Code / Cline) nutzen wir ein Set dedizierter Hilfs-MCP-Server:

### 4.1 codebase-index
- **Beschreibung**: Indexiert die gesamte Codebasis lokal in einer Cache-Datei (`.codebase-index-cache.pkl`) und ermöglicht extrem schnelle Suchen und Imports-Analysen, um Token-Kosten massiv zu reduzieren.
- **Wichtigste Tools**: `get_project_summary`, `list_files`, `search_codebase`, `get_structure_summary`, `find_symbol`, `get_dependencies`.

### 4.2 codet5-jepa
- **Beschreibung**: Führt semantische Suchen und Codegenerierung auf Basis eines lokalen Salesforce CodeT5+ Modells (Zero-Shot) aus. Besitzt ein lokales Lern-Netzwerk (PredictorNet) mit Experience Replay Buffer (ChromaDB), um aus akzeptierten Code-Iterationen direkt lokal zu lernen.
- **Wichtigste Tools**: `generate_jepa_plan`, `suggest_code`, `diff_merge_code`, `register_accepted_sample`, `batch_train`.
- **Einschränkung**: Das Tool `evaluate_code_energy` ist im Roo Code Setup global blockiert.

### 4.3 semantic-code-translator
- **Beschreibung**: Komprimiert Dateiinhalte (>100 Zeilen) und Signaturen, um den Tokenverbrauch im LLM-Kontextfenster drastisch zu reduzieren.
- **Wichtigste Tools**: `get_compressed_file`, `write_compressed_file`, `compress_context`.

### 4.4 obsidian-brain
- **Beschreibung**: Stellt der Coding-KI direkten Lese- und Schreibzugriff auf dieses Obsidian-Gehirn (`/werkai/`) zur Verfügung, um Rollen und API-Schnittstellen live synchron zu halten.
- **Wichtigste Tools**: `read_note`, `search_notes`, `write_memory_entry`, `append_to_note`.

### 4.5 local-router
- **Beschreibung**: Klassifiziert eingehende Benutzeranfragen und übersetzt die Ergebnisse am Ende in professionelle Zusammenfassungen.
- **Wichtigste Tools**: `classify_task`, `summarize_result`.

### 4.6 code-understanding
- **Beschreibung**: Bietet semantische Ähnlichkeitssuchen in bestehenden Implementierungen an, um das Rad nicht neu zu erfinden.
- **Wichtigste Tools**: `semantic_code_search`, `find_similar_implementation`.
