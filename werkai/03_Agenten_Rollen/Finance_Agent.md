# 🤖 Finance-Agent (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der Finance-Agent ist für die Buchhaltung, die Überwachung der Rechnungsstellung und das Mahnwesen im Betrieb zuständig. Er hilft, den Cashflow transparent zu halten.

## 2. Aufgaben & Fähigkeiten
- **Rechnungsprüfung**: Abgleich von eingehenden Rechnungen mit Lieferscheinen und Bestellungen (OCR-Extraktion).
- **Mahnwesen**: Automatisches Erkennen von überfälligen Zahlungen in PostgreSQL/Baserow und Erstellung von freundlichen Mahnungs-Entwürfen (Draft-Modus).
- **Finanzprognosen**: Auswertung von Kontoständen und offenen Forderungen, um Liquiditätsengpässe frühzeitig zu melden.

## 3. Tooling & Integrationen
- **ERP/Datenbank-Schnittstelle**: Zugriff auf historische Umsätze und offene Posten via [[ERP_Experte|ERP-Experte]].
- **Document-Parser**: Python-Bibliotheken (z.B. PyPDF, pdfplumber) zur Extraktion von Rechnungsdaten.
- **Reporting**: Generierung von einfachen Excel/CSV-Exports und PDF-Berichten (unterstützt vom [[Designer_Agent|Designer-Agenten]]).
