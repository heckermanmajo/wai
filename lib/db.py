"""Engine-Factories für die drei logischen DBs.

Env-Vars:
    ADMIN_DB_URL              -> postgresql+psycopg://user:pw@host:5432/admin_db
    LOGGING_DB_URL            -> postgresql+psycopg://user:pw@host:5432/logging_db
    TENANT_DB_URL_TEMPLATE    -> postgresql+psycopg://user:pw@host:5432/tenant_{slug}
                                 ({slug} wird beim Auflösen ersetzt)

Engines werden gecached — pro Prozess gibt es genau einen Engine pro DB-URL.
Sessions werden NICHT global gecached: Caller erzeugen sich eine Session
per `with session_for_tenant(slug) as s:` (oder _admin / _logging).
"""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from lib.slugify import is_valid_slug

_engines: dict[str, Engine] = {}
_lock = threading.Lock()


def _get_engine(url: str) -> Engine:
    eng = _engines.get(url)
    if eng is not None:
        return eng
    with _lock:
        eng = _engines.get(url)
        if eng is None:
            eng = create_engine(url, pool_pre_ping=True, future=True)
            _engines[url] = eng
        return eng


def admin_engine() -> Engine:
    url = os.environ.get("ADMIN_DB_URL")
    if not url:
        raise RuntimeError("ADMIN_DB_URL nicht gesetzt")
    return _get_engine(url)


def logging_engine() -> Engine:
    url = os.environ.get("LOGGING_DB_URL")
    if not url:
        raise RuntimeError("LOGGING_DB_URL nicht gesetzt")
    return _get_engine(url)


def tenant_db_url(slug: str) -> str:
    if not is_valid_slug(slug):
        raise ValueError(f"Ungültiger Tenant-Slug: {slug!r}")
    template = os.environ.get("TENANT_DB_URL_TEMPLATE")
    if not template:
        raise RuntimeError("TENANT_DB_URL_TEMPLATE nicht gesetzt")
    return template.replace("{slug}", slug)


def tenant_engine(slug: str) -> Engine:
    return _get_engine(tenant_db_url(slug))


def server_url_without_db() -> str:
    """Connection-URL zum Postgres-Server ohne konkrete DB — für CREATE DATABASE.

    Wird aus ADMIN_DB_URL abgeleitet (gleicher Host/User/Passwort).
    """
    url = os.environ.get("ADMIN_DB_URL")
    if not url:
        raise RuntimeError("ADMIN_DB_URL nicht gesetzt")
    # rstrip trailing '/<dbname>'
    base, _, _ = url.rpartition("/")
    return f"{base}/postgres"


@contextmanager
def session_for_admin() -> Iterator[Session]:
    sm = sessionmaker(bind=admin_engine(), expire_on_commit=False, future=True)
    with sm() as s:
        yield s


@contextmanager
def session_for_logging() -> Iterator[Session]:
    sm = sessionmaker(bind=logging_engine(), expire_on_commit=False, future=True)
    with sm() as s:
        yield s


@contextmanager
def session_for_tenant(slug: str) -> Iterator[Session]:
    sm = sessionmaker(bind=tenant_engine(slug), expire_on_commit=False, future=True)
    with sm() as s:
        yield s
