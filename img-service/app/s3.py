import io
import os

from minio import Minio
from PIL import Image

S3_HOST = os.environ["S3_HOST"]
S3_PORT = os.environ["S3_PORT"]
S3_USER = os.environ["S3_USER"]
S3_PASS = os.environ["S3_PASS"]

UPLOAD_BUCKET = "upload"
ORIGINAL_BUCKET = "original"

_client = Minio(
    f"{S3_HOST}:{S3_PORT}",
    access_key=S3_USER,
    secret_key=S3_PASS,
    secure=False,
)

PREVIEW_SIZES = {
    "large": (1024, 1024),
    "medium": (512, 512),
    "small": (128, 128),
}


def get_object(bucket: str, object_name: str) -> bytes:
    response = _client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def put_jpeg(bucket: str, object_name: str, data: bytes) -> None:
    _client.put_object(
        bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type="image/jpeg",
    )


def copy_to_original(object_key: str, filename: str, data: bytes | None = None) -> int:
    if data is None:
        data = get_object(UPLOAD_BUCKET, object_key)
    _client.put_object(
        ORIGINAL_BUCKET,
        filename,
        io.BytesIO(data),
        length=len(data),
    )
    return len(data)


def remove_upload(object_key: str) -> None:
    _client.remove_object(UPLOAD_BUCKET, object_key)


def create_previews(image_data: bytes, image_id: str) -> dict[str, int]:
    img = Image.open(io.BytesIO(image_data))
    if img.mode != "RGB":
        img = img.convert("RGB")

    sizes = {}
    for bucket, dimensions in PREVIEW_SIZES.items():
        preview = img.copy()
        preview.thumbnail(dimensions, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        preview.save(buf, format="JPEG", quality=85)
        jpeg_data = buf.getvalue()
        put_jpeg(bucket, f"{image_id}.jpeg", jpeg_data)
        sizes[bucket] = len(jpeg_data)
    return sizes


def check_s3() -> bool:
    try:
        _client.list_buckets()
        return True
    except Exception:
        return False
