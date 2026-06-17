# 🤖 Kalender-Agent (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der Kalender-Agent koordiniert Kunden- und Handwerker-Termine (z.B. Besprechungen, Aufmaß-Termine vor Ort, Montage-Einsätze). Er stellt sicher, dass keine Termin-Kollisionen auftreten und Termine logisch strukturiert sind.

## 2. Aufgaben & Fähigkeiten
- **Terminvorschläge**: Extraktion von Terminwünschen aus E-Mails oder WhatsApp-Chats und Abgleich mit dem Kalender.
- **Terminbuchung**: Erstellung von Kalendereinträgen und Senden von Einladungen (Draft-Modus).
- **Benachrichtigungen**: Automatische Erinnerungen an Kunden via WhatsApp vor dem Vor-Ort-Termin, um Leerfahrten zu vermeiden.

## 3. Tooling & Integrationen
- **Kalender-API**: Anbindung an Google Calendar oder Microsoft Outlook (in der Regel über n8n-Nodes gelöst).
- **Messaging**: WhatsApp Business API zur Absprache und Erinnerung.
- **Freigabe**: Bevor Termine endgültig gebucht werden, müssen sie über den Service-Layer und das Baserow-CRM freigegeben werden.
