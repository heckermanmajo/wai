-- Bootstrap für das wai-Demo-Setup.
-- Erzeugt die drei logischen Datenbanken (Admin / Logging / Tenant-Demo)
-- und aktiviert pgvector in jeder.

CREATE DATABASE admin_db;
CREATE DATABASE logging_db;
CREATE DATABASE tenant_demo;

\c admin_db
CREATE EXTENSION IF NOT EXISTS vector;

\c logging_db
CREATE EXTENSION IF NOT EXISTS vector;

\c tenant_demo
CREATE EXTENSION IF NOT EXISTS vector;
