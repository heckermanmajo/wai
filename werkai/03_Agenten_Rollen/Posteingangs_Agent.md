# 🤖 Posteingangs-Agent (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der Posteingangs-Agent fungiert als digitaler Poststellen-Mitarbeiter. Sein Hauptziel ist die automatische Ingestion, Strukturierung, Klassifizierung und Vorbereitung von Antwortentwürfen für eingehende E-Mails im Handwerksbetrieb.

## 2. Aufgaben & Fähigkeiten
- **Klassifizierung**: Erkennung von E-Mail-Kategorien (z.B. Ausschreibung, Rechnung, Reklamation, Initiativbewerbung, Spam).
- **Entwurfs-Erstellung (Drafting)**: Generierung von präzisen Antwort-Entwürfen auf Basis von E-Mail-Inhalten (z.B. Bestätigung des E-Mail-Eingangs, Anfordern fehlender Dokumente).
- **Delegation**: Zuweisung von E-Mails an spezialisierte Agenten (z.B. Rechnungen an den [[Finance_Agent|Finance-Agenten]], Bewerbungen an den [[HR_Agent|HR-Agenten]]).

## 3. Tooling & Integrationen
- **E-Mail-Verbindung**: IMAP-Ingestion (Lesen) und SMTP (Antwort-Entwürfe senden) gesteuert über n8n.
- **LLM-Klassifizierung**: Nutzung von Tier 1 LLMs zur schnellen Inhaltsanalyse und Tier 2 für hochwertige Antwort-Formulierungen.
- **Speicherung**: Ablage der klassifizierten E-Mails und Entwürfe in PostgreSQL und Bereitstellung im Baserow-CRM zur Freigabe durch den Mitarbeiter.
