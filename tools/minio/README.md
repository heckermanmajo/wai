# minio

**Typ:** Tool
**Status:** Skeleton

## Zweck
Object-Storage-Zugriff für File-Uploads/-Downloads (Belege, Verträge, Bilder, generierte Reports). S3-kompatible API via MinIO.

## API (Entwurf)
- `put(tenant_id, key, bytes, metadata)` — Upload, gibt File-ID zurück
- `get(tenant_id, key)` — Download (Stream)
- `presign(tenant_id, key, ttl)` — temporäre URL für Frontend-Upload/-Download
- `delete(tenant_id, key)`
- `list(tenant_id, prefix)`

## Konventionen
- Bucket pro Tenant (`tenant-<id>`) — Isolation
- Key-Schema: `<entity_type>/<entity_id>/<filename>`
- `File`-Eintrag in Tenant-DB hält Metadaten + Storage-Key

## Abhängigkeiten
- MinIO-Server
- Tenant-DB für `File`-Metadaten
