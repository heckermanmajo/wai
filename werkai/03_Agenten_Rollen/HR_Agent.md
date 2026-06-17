# 🤖 HR-Agent (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der HR-Agent unterstützt den Handwerksbetrieb beim Recruiting und der Mitarbeiterverwaltung. Angesichts des Fachkräftemangels im Handwerk liegt der Fokus auf einem schnellen, unkomplizierten Bewerbungsprozess (KI-Recruiting-Funnel).

## 2. Aufgaben & Fähigkeiten
- **Recruiting-Funnel**: Erfassung von Bewerberdaten über Tally.so oder Typeform.
- **Bewerber-Ingestion**: Automatisches Auslesen von Lebensläufen, die via E-Mail eingehen (durch Delegation vom [[Posteingangs_Agent|Posteingangs-Agenten]]).
- **Bewerbungs-Entwürfe**: Automatisches Vorbereiten von Einladungen zu Bewerbungsgesprächen oder Absagen (Draft-Modus).
- **Mitarbeiterverwaltung**: Pflege von Urlaubsansprüchen und Arbeitszeit-Erfassungen.

## 3. Tooling & Integrationen
- **Bewerbungs-Eingang**: Tally.so / Typeform (DSGVO-konform) via n8n.
- **Dokumentenanalyse**: OCR- und PDF-Parser in Python, um Lebensläufe semantisch zu strukturieren (Nutzung von Tier 2 LLMs).
- **CRM-Ablage**: Speicherung der Kandidaten-Daten in PostgreSQL/Baserow zur Sichtung durch die Geschäftsleitung.
