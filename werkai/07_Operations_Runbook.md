# ⚙️ Operations & Deployment Runbook

Dieses Dokument beschreibt die Betriebsprozesse, das Server-Setup und die Bereitstellungsschritte (Deployment) für Handwerk AI auf self-hosted Hetzner-Servern.

---

## 1. Multi-Tenant Docker Compose Architektur

Jeder Handwerksbetrieb (Mandant) erhält einen isolierten Container-Stack, um eine absolute Daten- und Prozess-Trennung gemäß DSGVO zu gewähren.

### System-Architektur (Docker-Netzwerk)

```mermaid
graph TD
    Client[Browser / WhatsApp / E-Mail] -->|HTTPS| Traefik{Traefik Reverse Proxy}
    Traefik -->|Port 8000| Tenant_A_Gateway[Tenant A: Gateway API]
    Traefik -->|Port 5678| Tenant_A_n8n[Tenant A: n8n Workflow Engine]
    
    Tenant_A_Gateway --> Tenant_A_Manager[Tenant A: Manager Agent]
    Tenant_A_n8n --> Tenant_A_Gateway
    
    Tenant_A_Gateway --> Tenant_A_DB[(Tenant A: PostgreSQL)]
    Tenant_A_Manager --> Tenant_A_DB
```

---

## 2. Docker Compose Template (`docker-compose.yml`)

Für jeden Mandanten wird ein separates Verzeichnis (z.B. `/opt/handwerkai/tenant-name/`) angelegt. Das Template für den Betrieb sieht wie folgt aus:

```yaml
version: '3.8'

services:
  database:
    image: postgres:15-alpine
    container_name: tenant_${TENANT_ID}_postgres
    restart: always
    environment:
      POSTGRES_DB: handwerkai_${TENANT_ID}
      POSTGRES_USER: admin_${TENANT_ID}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - internal

  gateway:
    image: handwerkai/gateway:latest
    container_name: tenant_${TENANT_ID}_gateway
    restart: always
    environment:
      - DATABASE_URL=postgresql://admin_${TENANT_ID}:${DB_PASSWORD}@database:5432/handwerkai_${TENANT_ID}
      - SECRET_KEY=${JWT_SECRET}
      - TENANT_ID=${TENANT_ID}
    depends_on:
      - database
    networks:
      - internal
      - public
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.tenant_${TENANT_ID}.rule=Host(`${DOMAIN}`)"
      - "traefik.http.routers.tenant_${TENANT_ID}.entrypoints=websecure"
      - "traefik.http.routers.tenant_${TENANT_ID}.tls.certresolver=letsencrypt"

  n8n:
    image: docker.n8n.io/n8nio/n8n:latest-debian
    container_name: tenant_${TENANT_ID}_n8n
    restart: always
    environment:
      - N8N_HOST=${DOMAIN}
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - N8N_ENCRYPTION_KEY=${N8N_ENC_KEY}
    volumes:
      - n8ndata:/home/node/.n8n
    networks:
      - internal
      - public
    depends_on:
      - database

networks:
  internal:
    driver: bridge
  public:
    external: true
    name: traefik_public

volumes:
  pgdata:
  n8ndata:
```

---

## 3. Operations-Routinen (Wartung & Sicherheit)

### 3.1 Tägliches Backup-Skript
Das Skript sichert die PostgreSQL-Datenbank und die n8n-Dateien verschlüsselt auf einen Hetzner Storage Box Backup-Speicher.

Pfad auf dem Host: `/opt/handwerkai/scripts/backup.sh`

```bash
#!/bin/bash
# Backup-Variablen
BACKUP_DIR="/mnt/backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TENANT_NAME="maler-schmidt"

echo "[+] Starte Backup für Mandant: ${TENANT_NAME}..."

# PostgreSQL Dump ziehen
docker exec -t tenant_1_postgres pg_dumpall -U admin_1 > ${BACKUP_DIR}/db_${TENANT_NAME}_${TIMESTAMP}.sql

# Komprimieren und verschlüsseln
tar -czf ${BACKUP_DIR}/data_${TENANT_NAME}_${TIMESTAMP}.tar.gz /opt/handwerkai/${TENANT_NAME}/

# Logs aufräumen (älter als 30 Tage)
find ${BACKUP_DIR} -type f -mtime +30 -delete

echo "[+] Backup erfolgreich abgeschlossen."
```

### 3.2 SSL-Zertifikate (Traefik/Let's Encrypt)
Traefik verwaltet SSL-Zertifikate vollautomatisch. Die Konfigurationsdatei `/opt/traefik/traefik.yml` steuert den Renewal-Prozess:

```yaml
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
  websecure:
    address: ":443"

certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@handwerk.ai
      storage: acme.json
      httpChallenge:
        entryPoint: web
```

---

## 4. Runbook: Neuen Mandanten anlegen

Folge diesen Schritten, um einen neuen Handwerksbetrieb auf dem Server zu provisionieren:

1. **DNS-Eintrag setzen**: Erstelle einen Subdomain-A-Record (z.B. `schmidt.handwerk.ai`) auf die IP des Hetzner-Servers.
2. **Ordnerstruktur vorbereiten**:
   ```bash
   mkdir -p /opt/handwerkai/maler-schmidt
   cd /opt/handwerkai/maler-schmidt
   ```
3. **`.env`-Konfigurationsdatei anlegen**:
   Trage die Passwörter und die Domain (`schmidt.handwerk.ai`) in die `.env` ein.
4. **Stack starten**:
   ```bash
   docker compose up -d
   ```
5. **n8n initialisieren**: Logge dich in n8n ein und importiere das Standard-Webhook-Routing für WhatsApp und E-Mail.
6. **Datenbank-Migrationen ausführen**:
   ```bash
   docker exec -it tenant_schmidt_gateway alembic upgrade head
   ```
