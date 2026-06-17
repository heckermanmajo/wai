# 🤖 ERP-Experte (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der ERP-Experte dient als Schnittstelle zu den bestehenden ERP-, CRM- und Branchensoftware-Systemen des Handwerksbetriebs (z.B. Streit V.1, KWP, pds, Lexware). 

## 2. Aufgaben & Fähigkeiten
- **Schnittstellen-Routing**: Einholen von Kundendaten, Materialbeständen oder Projektfortschritten aus der lokalen oder Cloud-ERP-Software.
- **Sub-Agenten pro System**: Da jeder Handwerker eine andere ERP-Software nutzt, wird der ERP-Experte modular konzipiert. Pro Branchensoftware wird ein spezifischer Sub-Agent (z.B. `KWP_SubAgent`, `Streit_SubAgent`) erstellt, der die jeweilige API oder Datenbank-Struktur beherrscht.
- **Datensynchronisation**: Aktualisierung von Adressdaten oder Projektstatus bei Änderungen im CRM oder WhatsApp.

## 3. Tooling & Integrationen
- **APIs / SQL-Brücken**: Datenbankzugriffe (teilweise über lokale SQL-Wrapper/MCP-Server) auf die ERP-Datenbanken.
- **n8n / Python Services**: Kapselung der API-Calls in standardisierte Python-Funktionen, um Slop und direkte DB-Kopplung zu vermeiden.
