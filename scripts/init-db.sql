-- Bootstrap für das wai-Setup.
-- Erzeugt die zentralen Datenbanken admin_db und logging_db und aktiviert
-- pgvector. Tenant-DBs (tenant_<slug>) werden NICHT hier angelegt — dafür
-- gibt es scripts/create_tenant.py, das pro Tenant CREATE DATABASE +
-- pgvector + alembic upgrade erledigt.

CREATE DATABASE admin_db;
CREATE DATABASE logging_db;

\c admin_db
CREATE EXTENSION IF NOT EXISTS vector;

\c logging_db
CREATE EXTENSION IF NOT EXISTS vector;
