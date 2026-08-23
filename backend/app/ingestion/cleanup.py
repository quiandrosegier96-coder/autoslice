"""Bounded cleanup for isolated upload workspaces."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from shutil import rmtree

from app.config import settings


def cleanup_stale_jobs(root: Path | None = None, retention_hours: int | None = None) -> int:
    """Remove UUID job directories older than the configured retention window."""
    upload_root = (root or settings.upload_dir).resolve()
    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=retention_hours if retention_hours is not None else settings.job_retention_hours
    )
    removed = 0
    if not upload_root.is_dir():
        return removed
    for candidate in upload_root.iterdir():
        if not candidate.is_dir():
            continue
        try:
            import uuid

            uuid.UUID(candidate.name)
        except ValueError:
            continue
        modified = datetime.fromtimestamp(candidate.stat().st_mtime, timezone.utc)
        if modified < cutoff and candidate.resolve().parent == upload_root:
            rmtree(candidate)
            removed += 1
    return removed
