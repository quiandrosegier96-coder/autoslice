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


ADMIN_EMAILS = {"admin2@autoslice.be"}


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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reset_tokens (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT    NOT NULL,
                token       TEXT    UNIQUE NOT NULL,
                created_at  TEXT    NOT NULL,
                used        INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_log (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id               TEXT NOT NULL,
                printer_id           TEXT,
                filament_type        TEXT,
                nozzle_size_mm       REAL,
                bbox_x               REAL,
                bbox_y               REAL,
                bbox_z               REAL,
                volume_cm3           REAL,
                surface_area_mm2     REAL,
                contact_area_mm2     REAL,
                height_to_base_ratio REAL,
                overhang_ratio       REAL,
                bridge_span_mm       REAL,
                thin_wall_mm         REAL,
                support_risk         INTEGER,
                adhesion_risk        INTEGER,
                stability_risk       INTEGER,
                detail_risk          INTEGER,
                settings_json        TEXT,
                created_at           TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS print_feedback (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT NOT NULL,
                user_id     INTEGER,
                outcome     TEXT NOT NULL,
                notes       TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        conn.commit()


def seed_admin_users() -> None:
    """Create default admin accounts on first boot if they don't exist yet."""
    from datetime import datetime, timezone
    from app.auth.service import hash_password
    created_at = datetime.now(timezone.utc).isoformat()
    accounts = [
        ("admin2", "admin2@autoslice.be", "AutoSlice2026!"),
    ]
    with get_connection() as conn:
        for username, email, password in accounts:
            exists = conn.execute(
                "SELECT 1 FROM users WHERE email = ?", (email,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO users (username, email, password_hash, created_at) VALUES (?,?,?,?)",
                    (username, email, hash_password(password), created_at),
                )
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


def log_generation(
    job_id: str,
    printer_id: str,
    filament_type: str,
    nozzle_size_mm: float,
    geometry,       # GeometryAnalysis
    intent,         # ModelIntent
    settings_json: str,
) -> None:
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()
    bb = geometry.bounding_box
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO generation_log (
                job_id, printer_id, filament_type, nozzle_size_mm,
                bbox_x, bbox_y, bbox_z, volume_cm3, surface_area_mm2,
                contact_area_mm2, height_to_base_ratio,
                overhang_ratio, bridge_span_mm, thin_wall_mm,
                support_risk, adhesion_risk, stability_risk, detail_risk,
                settings_json, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id, printer_id, filament_type, nozzle_size_mm,
                bb.x_mm, bb.y_mm, bb.z_mm, bb.volume_cm3,
                geometry.surface_area_mm2, geometry.contact_area_mm2,
                geometry.height_to_base_ratio,
                geometry.overhang.overhang_area_ratio,
                geometry.bridge.max_span_mm,
                geometry.thin_wall.min_thickness_mm,
                intent.support_risk, intent.adhesion_risk,
                intent.stability_risk, intent.detail_risk,
                settings_json, created_at,
            ),
        )
        conn.commit()


def log_feedback(job_id: str, user_id: int | None, outcome: str, notes: str | None = None) -> None:
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO print_feedback (job_id, user_id, outcome, notes, created_at) VALUES (?,?,?,?,?)",
            (job_id, user_id, outcome, notes, created_at),
        )
        conn.commit()
