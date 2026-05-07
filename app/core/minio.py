from datetime import timedelta
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

settings = get_settings()

# Read-only MinIO client — files are written by the camera AI pipeline, not this API
_client = Minio(
    endpoint=settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)


def normalize_object_path(object_path: str) -> str:
    """
    Normalize a MinIO object path to bucket-relative form.

    Some records already store paths prefixed with the bucket name. MinIO expects
    only the object key when signing or building a direct URL.
    """
    normalized = object_path.lstrip("/")
    bucket_prefix = f"{settings.MINIO_BUCKET.strip('/')}/"
    if normalized.startswith(bucket_prefix):
        normalized = normalized[len(bucket_prefix):]
    return normalized


def generate_presigned_url(object_path: str, expires_in_seconds: Optional[int] = None) -> tuple[str, int]:
    """
    Generate a temporary download URL for a file stored by the camera AI pipeline.

    Args:
        object_path : path inside bucket  e.g. "cameras/cam-01/clips/clip.mp4"

    Returns:
        (url, expires_in_seconds)
    """
    expiry_seconds = expires_in_seconds or settings.MINIO_URL_EXPIRES_SECONDS
    return generate_presigned_url_with_expiry(object_path, expiry_seconds)


def generate_presigned_url_with_expiry(object_path: str, expires_in_seconds: int) -> tuple[str, int]:
    """
    Generate a temporary download URL with a caller-provided expiry window.

    Args:
        object_path: path inside bucket.
        expires_in_seconds: presigned URL lifetime in seconds.

    Returns:
        (url, expires_in_seconds)
    """
    object_name = normalize_object_path(object_path)
    expires = timedelta(seconds=expires_in_seconds)
    url = _client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_name,
        expires=expires,
    )
    return url, expires_in_seconds
