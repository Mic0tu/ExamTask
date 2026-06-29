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


def get_image(image_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM image WHERE id = %s", (image_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def update_status(image_id: str, status: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE image SET status = %s WHERE id = %s",
                (status, image_id),
            )
        conn.commit()


def update_ready(
    image_id: str,
    original_size: int,
    large_size: int,
    medium_size: int,
    small_size: int,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE image
                SET status = 'ready',
                    original_size = %s,
                    large_size = %s,
                    medium_size = %s,
                    small_size = %s
                WHERE id = %s
                """,
                (original_size, large_size, medium_size, small_size, image_id),
            )
        conn.commit()


def check_db() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False
