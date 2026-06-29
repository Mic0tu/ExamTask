import os
from datetime import timedelta
from urllib.parse import urlparse

from minio import Minio

S3_HOST = os.environ["S3_HOST"]
S3_PORT = os.environ["S3_PORT"]
S3_USER = os.environ["S3_USER"]
S3_PASS = os.environ["S3_PASS"]
S3_EXTERNAL_URL = os.environ["S3_EXTERNAL_URL"].rstrip("/")

UPLOAD_BUCKET = "upload"

_client = Minio(
    f"{S3_HOST}:{S3_PORT}",
    access_key=S3_USER,
    secret_key=S3_PASS,
    secure=False,
)


def _external_client() -> Minio:
    parsed = urlparse(S3_EXTERNAL_URL)
    secure = parsed.scheme == "https"
    port = parsed.port or (443 if secure else 80)
    return Minio(
        f"{parsed.hostname}:{port}",
        access_key=S3_USER,
        secret_key=S3_PASS,
        secure=secure,
    )


def ensure_buckets() -> None:
    for bucket in ("upload", "original", "large", "medium", "small"):
        if not _client.bucket_exists(bucket):
            _client.make_bucket(bucket)


def get_presigned_upload_url(object_key: str) -> str:
    external = _external_client()
    return external.presigned_put_object(
        UPLOAD_BUCKET,
        object_key,
        expires=timedelta(hours=1),
    )


def check_s3() -> bool:
    try:
        _client.list_buckets()
        return True
    except Exception:
        return False
