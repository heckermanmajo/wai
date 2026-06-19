"""Alembic-env für tenant_<slug>.

Slug wird per `-x tenant_slug=<slug>` übergeben:
    alembic -c alembic-tenant.ini -x tenant_slug=demo upgrade head
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from lib.base import TenantBase  # noqa: E402
from lib.db import tenant_db_url  # noqa: E402
import lib.entities.tenant  # noqa: E402,F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = TenantBase.metadata


def _get_url() -> str:
    xargs = context.get_x_argument(as_dictionary=True)
    slug = xargs.get("tenant_slug")
    if not slug:
        raise RuntimeError(
            "tenant_slug fehlt — Aufruf mit `-x tenant_slug=<slug>`"
        )
    return tenant_db_url(slug)


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {}) or {}
    cfg["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
