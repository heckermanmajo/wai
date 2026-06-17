# websearch

**Typ:** Tool
**Status:** Skeleton

## Zweck
Externe Web-Suche für Agents (primär `researcher`, `sales_support`, `law`). Abstrahiert über mögliche Provider (Brave/Bing/…); Caller bleibt providerneutral.

## API (Entwurf)
- `search(query, k=10, lang, region)` — Top-Treffer mit URL/Title/Snippet
- `fetch(url)` — Inhalt einer Seite holen (cleaned)

## Konventionen
- Rate-Limit pro Tenant
- Ergebnisse cachen (Redis) — gleiche Query innerhalb TTL nicht erneut abrechnen
- Alle Calls in Logging-DB (Audit + Cost-Tracking)

## Abhängigkeiten
- Such-Provider (Konfig)
- Redis (Cache)
