# embeddings_search

**Typ:** Tool
**Status:** Skeleton

## Zweck
Semantische Suche über Tenant-Inhalte (Notes, Files, Messages, Norms, …) per Vektor-Embeddings. Standard-Backend: **pgvector** in der Tenant-DB.

## API (Entwurf)
- `index(tenant_id, entity_type, entity_id, text)` — embedded und ablegen
- `search(tenant_id, query, k=10, filter={entity_type, ...})` — Top-K
- `reindex(tenant_id, entity_type)` — Bulk-Refresh nach Modell-Wechsel

## Embedding-Modell
- TBD — beim Setzen die genutzte Modell-Version mitspeichern, damit Reindex erkennbar ist.

## Abhängigkeiten
- Postgres + pgvector (oder externes Vector-DB)
- Embedding-API (OpenAI/Anthropic/…)
