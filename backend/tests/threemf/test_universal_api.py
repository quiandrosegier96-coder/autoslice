from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes import universal_convert as route


@pytest.mark.asyncio
async def test_universal_endpoint_is_feature_flag_gated(monkeypatch):
    monkeypatch.setattr(route.settings, "use_universal_3mf_engine", False)
    request = route.UniversalConvertRequest(job_id="missing", target_printer="kobra-s1")

    with pytest.raises(HTTPException) as caught:
        await route.universal_convert(request, {"sub": "7"})

    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "UNIVERSAL_ENGINE_DISABLED"


@pytest.mark.asyncio
async def test_download_is_owner_scoped(tmp_path: Path):
    conversion_id = "owner-scope-test"
    output = tmp_path / "model_AutoSlice.3mf"
    output.write_bytes(b"not exposed")
    with route._records_lock:
        route._records[conversion_id] = route._DownloadRecord(7, output, output.name)
    try:
        with pytest.raises(HTTPException) as caught:
            await route.universal_download(conversion_id, {"sub": "8"})
        assert caught.value.status_code == 404
    finally:
        with route._records_lock:
            route._records.pop(conversion_id, None)


@pytest.mark.asyncio
async def test_download_revalidates_output(tmp_path: Path):
    conversion_id = "validation-gate-test"
    output = tmp_path / "model_AutoSlice.3mf"
    output.write_bytes(b"invalid 3mf")
    with route._records_lock:
        route._records[conversion_id] = route._DownloadRecord(7, output, output.name)
    try:
        with pytest.raises(HTTPException) as caught:
            await route.universal_download(conversion_id, {"sub": "7"})
        assert caught.value.status_code == 409
    finally:
        with route._records_lock:
            route._records.pop(conversion_id, None)
