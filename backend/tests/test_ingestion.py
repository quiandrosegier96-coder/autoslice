"""Security and lifecycle tests for the ingestion boundary."""

import io
import os
from pathlib import Path
import time
import uuid
import zipfile

from fastapi import HTTPException, UploadFile
import pytest

from app.ingestion.cleanup import cleanup_stale_jobs
from app.ingestion.handler import create_job, find_job
from app.ingestion.unpacker import unpack
from app.ingestion.validator import validate_3mf_upload
from app.threemf.container.security import UnsafeThreeMFError


def archive(entries: dict[str, bytes] | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as package:
        for name, payload in (entries or {"3D/3dmodel.model": b"<model/>"}).items():
            package.writestr(name, payload)
    return output.getvalue()


def upload_file(name: str, payload: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(payload), size=len(payload))


@pytest.mark.asyncio
async def test_validator_rejects_non_3mf():
    with pytest.raises(HTTPException) as caught:
        await validate_3mf_upload(upload_file("model.zip", archive()))
    assert caught.value.status_code == 400


@pytest.mark.asyncio
async def test_validator_rejects_non_zip():
    with pytest.raises(HTTPException) as caught:
        await validate_3mf_upload(upload_file("model.3mf", b"not a zip"))
    assert caught.value.status_code == 400


def test_unpacker_maps_model_file(tmp_path: Path):
    source = tmp_path / "source.3mf"
    source.write_bytes(archive())
    result = unpack(source, tmp_path / "out")
    assert result.model_file == tmp_path / "out" / "3D" / "3dmodel.model"


def test_legacy_unpacker_rejects_path_traversal(tmp_path: Path):
    source = tmp_path / "source.3mf"
    source.write_bytes(archive({"../escape.model": b"secret"}))
    with pytest.raises(UnsafeThreeMFError):
        unpack(source, tmp_path / "out")
    assert not (tmp_path / "escape.model").exists()


@pytest.mark.asyncio
async def test_job_storage_never_uses_client_filename(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.ingestion.handler.settings.upload_dir", tmp_path)
    job = await create_job(upload_file("../private.3mf", archive()))
    assert job.archive_path.name == "source.3mf"
    assert job.archive_path.parent.parent == tmp_path
    assert job.original_filename == "private.3mf"


@pytest.mark.asyncio
async def test_streamed_upload_limit_is_enforced_and_partial_job_removed(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.ingestion.handler.settings.upload_dir", tmp_path)
    monkeypatch.setattr("app.ingestion.handler.settings.max_upload_size_mb", 0)
    with pytest.raises(HTTPException) as caught:
        await create_job(upload_file("large.3mf", archive()))
    assert caught.value.status_code == 413
    assert list(tmp_path.iterdir()) == []


def test_find_job_rejects_non_uuid_and_traversal(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.ingestion.handler.settings.upload_dir", tmp_path)
    assert find_job("../community/files") is None
    assert find_job("not-a-job-id") is None


def test_cleanup_removes_only_stale_uuid_workspaces(tmp_path: Path):
    stale = tmp_path / str(uuid.uuid4())
    fresh = tmp_path / str(uuid.uuid4())
    unrelated = tmp_path / "community"
    for path in (stale, fresh, unrelated):
        path.mkdir()
    old = time.time() - 7200
    os.utime(stale, (old, old))
    assert cleanup_stale_jobs(tmp_path, retention_hours=1) == 1
    assert not stale.exists()
    assert fresh.exists() and unrelated.exists()
