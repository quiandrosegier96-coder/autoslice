"""
AutoSlice — SQLite database setup for user authentication and generation logging.
"""

import json
import sqlite3
from pathlib import Path

from app.config import settings

DB_PATH = settings.db_path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


ADMIN_EMAILS = {"admin@autoslice.be", "admin2@autoslice.be", "quiandro@autoslice.be", "geoffroynick@network-it.be", "y.smets@hotmail.com"}


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT NOT NULL,
                user_id     INTEGER,
                stars       INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS community_prints (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                username       TEXT    NOT NULL,
                title          TEXT    NOT NULL,
                description    TEXT    DEFAULT '',
                filament_type  TEXT    DEFAULT '',
                printer_name   TEXT    DEFAULT '',
                filename       TEXT    NOT NULL,
                photo_filename TEXT    NOT NULL,
                download_count INTEGER DEFAULT 0,
                created_at     TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS community_ratings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                print_id   INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                stars      INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
                created_at TEXT    NOT NULL,
                UNIQUE(print_id, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verification_codes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                code_hash  TEXT    NOT NULL,
                created_at TEXT    NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS site_config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                text        TEXT    NOT NULL,
                app_version TEXT,
                approved    INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    NOT NULL,
                approved_at TEXT
            )
        """)
        # Schema migrations — add new columns to existing tables without data loss
        _add_column_if_missing(conn, "generation_log", "decision_trace_json", "TEXT")
        _add_column_if_missing(conn, "generation_log", "settings_delta_json",  "TEXT")
        _add_column_if_missing(conn, "users", "last_login",    "TEXT")
        _add_column_if_missing(conn, "users", "is_verified",   "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "users", "settings_json", "TEXT NOT NULL DEFAULT '{}'")
        _add_column_if_missing(conn, "users", "is_admin",      "INTEGER NOT NULL DEFAULT 0")
        # Sync ADMIN_EMAILS into is_admin column so DB is authoritative
        for email in ADMIN_EMAILS:
            conn.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (email,))
        conn.commit()


def seed_admin_users() -> None:
    """Create default admin accounts on first boot if they don't exist yet."""
    from datetime import datetime, timezone
    from app.auth.service import hash_password
    created_at = datetime.now(timezone.utc).isoformat()
    accounts = [
        ("admin",  "admin@autoslice.be",  "Admin@Autoslice2026!"),
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
            else:
                # Always sync password so known credentials stay valid across deployments
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE email = ?",
                    (hash_password(password), email),
                )
        conn.commit()


DEFAULT_SITE_CONFIG: dict = {
    "landing_features":   True,
    "landing_how":        True,
    "landing_pricing":    True,
    "landing_apppreview": True,
    "landing_multicolor": True,
    "landing_trustbar":   True,
    "landing_downloadcta":True,
    "nav_history":        True,
    "nav_community":      True,
    "nav_settings":       True,
    "registration_open":  True,
    "maintenance_mode":   False,
}


def get_site_config() -> dict:
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM site_config").fetchall()
    config = dict(DEFAULT_SITE_CONFIG)
    for row in rows:
        config[row["key"]] = json.loads(row["value"])
    return config


def set_site_config(updates: dict) -> dict:
    with get_connection() as conn:
        for key, value in updates.items():
            if key in DEFAULT_SITE_CONFIG:
                conn.execute(
                    "INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)",
                    (key, json.dumps(value)),
                )
        conn.commit()
    return get_site_config()


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


def log_generation_v2(
    job_id: str,
    printer_id: str,
    filament_type: str,
    nozzle_size_mm: float,
    geometry,           # GeometryAnalysis
    intent,             # ModelIntent
    settings_json: str,
    base_settings_json: str,
    trace,              # DecisionTrace
) -> None:
    """
    Extended generation log that also stores the decision trace
    and a settings delta (diff from base profile to final settings).
    """
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()
    bb = geometry.bounding_box
    delta = _diff_settings(base_settings_json, settings_json)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO generation_log (
                job_id, printer_id, filament_type, nozzle_size_mm,
                bbox_x, bbox_y, bbox_z, volume_cm3, surface_area_mm2,
                contact_area_mm2, height_to_base_ratio,
                overhang_ratio, bridge_span_mm, thin_wall_mm,
                support_risk, adhesion_risk, stability_risk, detail_risk,
                settings_json, decision_trace_json, settings_delta_json,
                created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                settings_json,
                json.dumps(trace.to_list()),
                json.dumps(delta),
                created_at,
            ),
        )
        conn.commit()


def get_generation_trace(job_id: str) -> dict | None:
    """Return the latest decision trace + settings delta for a job_id."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT decision_trace_json, settings_delta_json, settings_json,
                      support_risk, adhesion_risk, stability_risk, detail_risk,
                      filament_type, nozzle_size_mm, printer_id, created_at
               FROM generation_log
               WHERE job_id = ? AND decision_trace_json IS NOT NULL
               ORDER BY id DESC LIMIT 1""",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "job_id":            job_id,
            "printer_id":        row["printer_id"],
            "filament_type":     row["filament_type"],
            "nozzle_size_mm":    row["nozzle_size_mm"],
            "support_risk":      row["support_risk"],
            "adhesion_risk":     row["adhesion_risk"],
            "stability_risk":    row["stability_risk"],
            "detail_risk":       row["detail_risk"],
            "created_at":        row["created_at"],
            "decision_trace":    json.loads(row["decision_trace_json"] or "[]"),
            "settings_delta":    json.loads(row["settings_delta_json"] or "{}"),
        }


def log_feedback(job_id: str, user_id: int | None, outcome: str, notes: str | None = None) -> None:
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO print_feedback (job_id, user_id, outcome, notes, created_at) VALUES (?,?,?,?,?)",
            (job_id, user_id, outcome, notes, created_at),
        )
        conn.commit()


def submit_rating(job_id: str, user_id: int | None, stars: int) -> None:
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO ratings (job_id, user_id, stars, created_at) VALUES (?,?,?,?)",
            (job_id, user_id, stars, created_at),
        )
        conn.commit()


def get_average_rating() -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT ROUND(AVG(stars), 1) as avg, COUNT(*) as total FROM ratings"
        ).fetchone()
    return {"average": row["avg"] or 0.0, "total": row["total"] or 0}


def _diff_settings(base_json: str, final_json: str) -> dict:
    base  = json.loads(base_json)
    final = json.loads(final_json)
    return {k: {"from": base.get(k), "to": v}
            for k, v in final.items() if v != base.get(k)}
