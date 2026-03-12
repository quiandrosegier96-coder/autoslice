"""
AutoSlice — SQLite database setup for user authentication.
"""

import sqlite3
from pathlib import Path

from app.config import settings

DB_PATH = settings.upload_dir.parent / "autoslice.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


ADMIN_EMAILS = {"admin1@prints.be", "admin2@prints.be"}


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    UNIQUE NOT NULL,
                email       TEXT    UNIQUE NOT NULL,
                password_hash TEXT  NOT NULL,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT    NOT NULL,
                user_id     INTEGER,
                action      TEXT    NOT NULL,
                filename    TEXT,
                printer_id  TEXT,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.commit()


def log_job(job_id: str, user_id: int | None, action: str,
            filename: str | None = None, printer_id: str | None = None) -> None:
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, user_id, action, filename, printer_id, created_at) VALUES (?,?,?,?,?,?)",
            (job_id, user_id, action, filename, printer_id, created_at),
        )
        conn.commit()
