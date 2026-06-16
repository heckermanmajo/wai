# finance

**Typ:** Agent
**Status:** Skeleton

## Zweck
Buchhaltungs- und Finanz-Themen: Rechnungs-Verarbeitung, Belege kategorisieren, einfache Reports, Plausibilitätschecks.

## Verantwortlichkeiten
- Belege aus `minio` lesen, Daten extrahieren
- Buchungsvorschläge erstellen (User bestätigt)
- Reports erzeugen (Umsatz, Kosten, offene Posten)
- Anomalien flaggen

## Genutzte Tools
- `tools/minio` — Beleg-Files
- `tools/database_management` — Buchungs-Persistenz
- `tools/embeddings_search` — ähnliche frühere Buchungen finden

## DB-Zugriffe
- Tenant DB: `Item`, `Category`, `CategoryItem`, `File`

## MCP-Schnittstelle
TBD
