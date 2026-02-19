"""
MinIO Client — S3-compatible object storage for document files.
Replaces local filesystem storage for production use.
"""

import os
import io
from minio import Minio
from minio.error import S3Error

# Configuration from environment
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "vecvrag")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "vecvrag_minio_secret")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "vecvrag-documents")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Lazy-initialized client
_client: Minio = None


def _get_client() -> Minio:
    """Get or create the MinIO client singleton."""
    global _client
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        _ensure_bucket()
    return _client


def _ensure_bucket():
    """Create the bucket if it doesn't exist."""
    client = _client
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)
        print(f"Created MinIO bucket: {MINIO_BUCKET}")


def upload_file(
    file_path: str, object_name: str, content_type: str = "application/octet-stream"
) -> str:
    """
    Upload a local file to MinIO.

    Args:
        file_path: Path to the local file
        object_name: Name/key to store the file as in MinIO
        content_type: MIME type of the file

    Returns:
        The object_name (key) stored in MinIO
    """
    client = _get_client()
    client.fput_object(
        MINIO_BUCKET,
        object_name,
        file_path,
        content_type=content_type,
    )
    return object_name


def upload_bytes(
    data: bytes, object_name: str, content_type: str = "application/octet-stream"
) -> str:
    """
    Upload raw bytes to MinIO.

    Args:
        data: Raw file bytes
        object_name: Name/key to store in MinIO
        content_type: MIME type

    Returns:
        The object_name
    """
    client = _get_client()
    client.put_object(
        MINIO_BUCKET,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def download_file(object_name: str, file_path: str) -> str:
    """
    Download a file from MinIO to a local path.

    Args:
        object_name: Key of the object in MinIO
        file_path: Local path to save the file

    Returns:
        The local file_path
    """
    client = _get_client()
    client.fget_object(MINIO_BUCKET, object_name, file_path)
    return file_path


def get_presigned_url(object_name: str, expires_hours: int = 1) -> str:
    """
    Generate a presigned URL for temporary access.

    Args:
        object_name: Key of the object
        expires_hours: How many hours the URL is valid

    Returns:
        Presigned URL string
    """
    from datetime import timedelta

    client = _get_client()
    return client.presigned_get_object(
        MINIO_BUCKET,
        object_name,
        expires=timedelta(hours=expires_hours),
    )


def delete_file(object_name: str) -> None:
    """Delete a file from MinIO."""
    client = _get_client()
    client.remove_object(MINIO_BUCKET, object_name)


def file_exists(object_name: str) -> bool:
    """Check if a file exists in MinIO."""
    client = _get_client()
    try:
        client.stat_object(MINIO_BUCKET, object_name)
        return True
    except S3Error:
        return False


def get_bucket_stats() -> dict:
    """Get basic stats about the bucket."""
    client = _get_client()
    objects = list(client.list_objects(MINIO_BUCKET, recursive=True))
    total_size = sum(obj.size for obj in objects)
    return {
        "total_files": len(objects),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "bucket": MINIO_BUCKET,
    }
