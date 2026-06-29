import logging
import os
import threading
from queue import Empty, Queue
from urllib.parse import unquote

import httpx

from app import db, s3

logger = logging.getLogger(__name__)

PUSH_ENDPOINT = os.environ["PUSH_ENDPOINT"]

_task_queue: Queue[str] = Queue()
_worker_started = False
_worker_lock = threading.Lock()


def _notify_push(image_id: str, user_id: str, status: str) -> None:
    payload = {
        "object": "image",
        "object_id": image_id,
        "user_id": str(user_id),
        "status": status,
    }
    try:
        response = httpx.post(
            PUSH_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        response.raise_for_status()
        logger.info("Push notification sent for image %s", image_id)
    except Exception as e:
        logger.error("Failed to notify push service: %s", e)


def _process_image(image_id: str) -> None:
    logger.info("Processing image %s", image_id)

    image = db.get_image(image_id)
    if image is None:
        logger.error("Image %s not found in database", image_id)
        return

    if image["status"] not in ("upload", "error"):
        logger.info("Image %s already processed (status=%s)", image_id, image["status"])
        return

    try:
        logger.info("Updating status to process for %s", image_id)
        db.update_status(image_id, "process")

        logger.info("Downloading from upload bucket: %s", image_id)
        data = s3.get_object(s3.UPLOAD_BUCKET, image_id)

        logger.info("Creating previews for %s", image_id)
        preview_sizes = s3.create_previews(data, image_id)

        logger.info("Moving original for %s", image_id)
        original_size = s3.copy_to_original(image_id, image["name"], data)

        logger.info("Removing upload object %s", image_id)
        s3.remove_upload(image_id)

        logger.info("Updating database for %s", image_id)
        db.update_ready(
            image_id,
            original_size,
            preview_sizes["large"],
            preview_sizes["medium"],
            preview_sizes["small"],
        )

        _notify_push(image_id, image["user_id"], "ready")
        logger.info("Image %s processed successfully", image_id)

    except Exception as e:
        logger.error("Error processing image %s: %s", image_id, e)
        try:
            db.update_status(image_id, "error")
            _notify_push(image_id, image["user_id"], "error")
        except Exception as inner:
            logger.error("Failed to update error status: %s", inner)


def _worker() -> None:
    while True:
        try:
            image_id = _task_queue.get(timeout=1)
        except Empty:
            continue
        try:
            _process_image(image_id)
        finally:
            _task_queue.task_done()


def start_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        _worker_started = True


def enqueue(image_id: str) -> None:
    _task_queue.put(image_id)


def extract_object_key(event: dict) -> str | None:
    records = event.get("Records", [])
    if records:
        key = records[0].get("s3", {}).get("object", {}).get("key", "")
        if key:
            return unquote(key.split("/")[-1])

    key = event.get("Key", "")
    if key:
        return unquote(key.split("/")[-1])

    return None
