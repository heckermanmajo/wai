"""MinIO-Helper — Bucket-Management und Up/Download.

Buckets werden pro Mandant angelegt: ``wai-tenant-<slug>`` (Underscores im Slug
werden zu Bindestrichen, da S3 keine Underscores im Bucket-Namen mag).

Object-Keys folgen dem Schema ``<source>/<yyyy>/<mm>/<uuid>.<ext>`` — die
Aufrufer-Seite ist fuer das Mapping in die DB (Tabelle ``attachment``)
zustaendig.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from minio import Minio
from minio.error import S3Error


def minio_client() -> Minio:
    endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "wai")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "wai_dev_minio")
    secure = os.environ.get("MINIO_SECURE", "false").lower() in ("1", "true", "yes")
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


def bucket_for_tenant(slug: str) -> str:
    """Liefert den S3-konformen Bucket-Namen fuer einen Tenant-Slug."""
    prefix = os.environ.get("MINIO_BUCKET_PREFIX", "wai-tenant")
    return f"{prefix}-{slug}".replace("_", "-")


def ensure_bucket(name: str) -> str:
    """Legt den Bucket idempotent an und liefert seinen Namen zurueck."""
    cli = minio_client()
    try:
        if not cli.bucket_exists(name):
            cli.make_bucket(name)
    except S3Error as exc:
        # BucketAlreadyOwnedByYou / BucketAlreadyExists sind ok
        if exc.code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise
    return name


def build_object_key(source: str, ext: str) -> str:
    """``<source>/<yyyy>/<mm>/<uuid>.<ext>`` (ext ohne fuehrenden Punkt)."""
    now = datetime.now(timezone.utc)
    safe_ext = (ext or "bin").lstrip(".").lower() or "bin"
    return f"{source}/{now:%Y}/{now:%m}/{uuid4().hex}.{safe_ext}"


def upload_bytes(
    bucket: str, key: str, data: bytes, content_type: str
) -> dict:
    """Laedt ``data`` als Object hoch und gibt Metadaten zurueck."""
    cli = minio_client()
    ensure_bucket(bucket)
    sha = hashlib.sha256(data).hexdigest()
    size = len(data)
    cli.put_object(
        bucket_name=bucket,
        object_name=key,
        data=BytesIO(data),
        length=size,
        content_type=content_type or "application/octet-stream",
    )
    return {"key": key, "size": size, "sha256": sha}


def download_bytes(bucket: str, key: str) -> bytes:
    cli = minio_client()
    resp = cli.get_object(bucket, key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def presigned_get_url(bucket: str, key: str, ttl_seconds: int = 3600) -> str:
    from datetime import timedelta

    cli = minio_client()
    return cli.presigned_get_object(bucket, key, expires=timedelta(seconds=ttl_seconds))
