from datetime import timedelta
from typing import BinaryIO

from minio import Minio

from app.settings import settings


def _client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_use_ssl,
    )


def _public_client() -> Minio:
    # Signed URLs are consumed by the browser, which cannot resolve the
    # Compose-internal MinIO hostname — sign against the public one instead.
    return Minio(
        settings.minio_public_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_use_ssl,
    )


def ensure_bucket() -> None:
    client = _client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def check_storage() -> bool:
    try:
        ensure_bucket()
        return True
    except Exception:  # noqa: BLE001 — health check must never raise
        return False


def put(key: str, data: BinaryIO, length: int, content_type: str) -> None:
    _client().put_object(
        settings.minio_bucket, key, data, length, content_type=content_type
    )


def get(key: str) -> BinaryIO:
    return _client().get_object(settings.minio_bucket, key)


def signed_url(key: str, expires: timedelta = timedelta(minutes=15)) -> str:
    return _public_client().presigned_get_object(
        settings.minio_bucket, key, expires=expires
    )
