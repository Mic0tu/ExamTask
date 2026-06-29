import os

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "port": int(os.environ["DB_PORT"]),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASS"],
    "dbname": os.environ["DB_NAME"],
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def insert_image(image_id: str, user_id: str, name: str, mime_type: str, size: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO image (id, user_id, name, mime_type, original_size, status)
                VALUES (%s, %s, %s, %s, %s, 'upload')
                """,
                (image_id, user_id, name, mime_type, size),
            )
        conn.commit()


def get_image(image_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM image WHERE id = %s", (image_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def check_db() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False
