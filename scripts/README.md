# scripts

**Status:** Skeleton (`start_local.sh` / `start_local.bat` sind leer).

## Zweck
Lokale Dev-/Ops-Helper, die nicht in die Anwendung selbst gehören.

## Skripte
- `start_local.sh` — komplettes Dev-Stack hochfahren (Docker-Compose + Migrations + Tenant `demo` + Dev-User-Seed)
- `start_local.bat` — Windows-Pendant (aktuell nur `docker compose up`, ohne Seed)
- `create_tenant.py <slug>` — neuen Tenant + DB + Migration anlegen; optional Admin-User via `--admin-username`
- `seed_admin.py [--tenant demo]` — Default-Dev-User (`demo`, `alice`) mit Passwort `123` im Tenant einhängen (idempotent)

## Geplant
- `reset_tenant.{sh|py}` — Tenant-DB zurücksetzen (mit Bestätigung — niemals ohne!)
- `tail_logs.sh` — gefilterter Live-Tail der Logging-DB

## Konventionen
- Skripte sind idempotent (mehrfach laufen lassen = gleicher Endzustand)
- Destructive Operations brauchen explizite Confirmation-Prompts
- Plattform-Parität: für jedes `.sh` ein `.bat` (oder eine plattformneutrale Python-Variante)
