#!/usr/bin/env sh
set -e
cd "$(dirname "$0")/.."
docker compose up --build -d "$@"

echo "[wait] Warte auf gesundes Gateway..."
for i in $(seq 1 30); do
    if docker compose ps gateway 2>/dev/null | grep -q "Up"; then
        break
    fi
    sleep 1
done

echo "[migrate] Admin-DB"
docker compose exec -T gateway alembic -c alembic-admin.ini upgrade head

echo "[migrate] Logging-DB"
docker compose exec -T gateway alembic -c alembic-logging.ini upgrade head

echo "[tenant] Lege Tenant 'demo' an (idempotent)"
docker compose exec -T gateway python scripts/create_tenant.py demo

echo "[seed] Dev-User in 'demo' anlegen (Passwort: 123)"
docker compose exec -T gateway python scripts/seed_admin.py --tenant demo

echo "[seed] Demo-Vorgaenge in 'demo' anlegen"
docker compose exec -T gateway python scripts/seed_tenant_demo.py --tenant demo

echo "[ok] Stack laeuft."
echo "      Backend-API:  http://localhost:8500"
echo "      Next.js-UI:   http://localhost:3000"
echo "      Traces:       http://localhost:3000/traces"
docker compose logs -f gateway interface mcp_mock
