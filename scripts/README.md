# scripts

**Status:** Skeleton (`start_local.sh` / `start_local.bat` sind leer).

## Zweck
Lokale Dev-/Ops-Helper, die nicht in die Anwendung selbst gehören.

## Geplante Skripte
- `start_local.sh` / `.bat` — komplettes Dev-Stack hochfahren (Docker-Compose + Migrations + Seed)
- `seed_admin.{sh|py}` — Default-Admin + Demo-Tenant anlegen
- `reset_tenant.{sh|py}` — Tenant-DB zurücksetzen (mit Bestätigung — niemals ohne!)
- `tail_logs.sh` — gefilterter Live-Tail der Logging-DB

## Konventionen
- Skripte sind idempotent (mehrfach laufen lassen = gleicher Endzustand)
- Destructive Operations brauchen explizite Confirmation-Prompts
- Plattform-Parität: für jedes `.sh` ein `.bat` (oder eine plattformneutrale Python-Variante)
