from datetime import timedelta

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


def generate_presigned_url(object_path: str) -> tuple[str, int]:
    """
    Generate a temporary download URL for a file stored by the camera AI pipeline.

    Args:
        object_path : path inside bucket  e.g. "cameras/cam-01/clips/clip.mp4"

    Returns:
        (url, expires_in_seconds)
    """
    expires = timedelta(seconds=settings.MINIO_URL_EXPIRES_SECONDS)
    url = _client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_path,
        expires=expires,
    )
    return url, settings.MINIO_URL_EXPIRES_SECONDS
