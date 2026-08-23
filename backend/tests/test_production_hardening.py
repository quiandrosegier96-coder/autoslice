"""Production release gates spanning API security, concurrency, and contracts."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient

from app.main import app
from app.config import Settings
from app.auth.dependencies import get_current_user
from app.threemf.conversion import convert_3mf
from app.threemf.domain.settings import ConversionContext


def test_job_routes_require_authentication():
    client = TestClient(app)
    job = "00000000-0000-0000-0000-000000000000"
    requests = (
        ("get", f"/api/upload/{job}/file", None),
        ("get", f"/api/analyze/{job}", None),
        ("get", f"/api/analyze/{job}/support-preview", None),
        ("get", f"/api/scoring/report/{job}", None),
        ("get", f"/api/support/{job}/engine", None),
        ("get", f"/api/ai/auto-settings/{job}", None),
        ("post", "/api/convert", {"job_id": job, "printer_id": "kobra-s1", "filament_type": "pla"}),
        ("post", "/api/universal-analyze", {"job_id": job, "target_printer": "kobra-s1"}),
        ("post", "/api/universal-convert", {"job_id": job, "target_printer": "kobra-s1"}),
    )
    for method, path, body in requests:
        response = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
        assert response.status_code == 401, (method, path, response.status_code, response.text)


def test_openapi_exposes_unique_route_method_contracts():
    schema = app.openapi()
    operations: list[str] = []
    for path in schema["paths"].values():
        for method, operation in path.items():
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                operations.append(operation["operationId"])
                assert "responses" in operation
    assert len(operations) == len(set(operations))
    assert len(operations) >= 35


def test_release_versions_are_compatible():
    root = Path(__file__).parents[2]
    frontend = json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))
    electron = json.loads((root / "electron" / "package.json").read_text(encoding="utf-8"))
    assert app.version == frontend["version"] == electron["version"] == "1.5.63"


def test_rollout_defaults_preserve_legacy_until_real_fixtures_are_certified():
    release_settings = Settings(jwt_secret_key="release-test-secret", _env_file=None)
    assert release_settings.use_universal_3mf_engine is False
    assert release_settings.universal_3mf_legacy_fallback is True


def _core_3mf_bytes() -> bytes:
    output = BytesIO()
    model = b'''<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><metadata name="Application">Bambu Studio</metadata><resources><object id="1" type="model"><mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="10" y="0" z="0"/><vertex x="0" y="10" z="0"/><vertex x="0" y="0" z="10"/></vertices><triangles><triangle v1="0" v2="2" v3="1"/><triangle v1="0" v2="1" v3="3"/><triangle v1="1" v2="2" v3="3"/><triangle v1="2" v2="0" v3="3"/></triangles></mesh></object></resources><build><item objectid="1"/></build></model>'''
    rels = b'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("_rels/.rels", rels)
        archive.writestr("3D/3dmodel.model", model)
    return output.getvalue()


def test_authenticated_upload_analyze_convert_validate_download_e2e(tmp_path, monkeypatch):
    import app.database as database
    import app.main as main

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "e2e.db")
    monkeypatch.setattr(main.settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(main.settings, "use_universal_3mf_engine", True)
    monkeypatch.setattr(main, "seed_admin_users", lambda: None)
    main.settings.upload_dir.mkdir()
    database.init_db()
    with database.get_connection() as connection:
        connection.execute(
            "INSERT INTO users (id, username, email, password_hash, created_at) VALUES (1, 'release', 'release@example.invalid', 'x', '2026-08-23T00:00:00+00:00')"
        )
        connection.commit()

    main.app.dependency_overrides[get_current_user] = lambda: {
        "sub": "1", "email": "release@example.invalid", "is_admin": False
    }
    try:
        with TestClient(main.app) as client:
            uploaded = client.post(
                "/api/upload",
                files={"file": ("e2e.3mf", _core_3mf_bytes(), "model/3mf")},
            )
            assert uploaded.status_code == 200, uploaded.text
            job_id = uploaded.json()["job_id"]

            analyzed = client.post(
                "/api/universal-analyze",
                json={"job_id": job_id, "target_printer": "kobra_s1"},
            )
            assert analyzed.status_code == 200, analyzed.text
            assert analyzed.json()["dry_run"] is True

            legacy = client.post(
                "/api/convert",
                json={
                    "job_id": job_id,
                    "printer_id": "kobra_s1",
                    "filament_type": "pla",
                },
            )
            assert legacy.status_code == 200, legacy.text
            assert legacy.content.startswith(b"PK")

            converted = client.post(
                "/api/universal-convert",
                json={"job_id": job_id, "target_printer": "kobra_s1"},
            )
            assert converted.status_code == 200, converted.text
            response = converted.json()
            assert response["validation_passed"] is True
            assert response["compatibility"]["pipeline_stages"]

            downloaded = client.get(response["download_reference"])
            assert downloaded.status_code == 200
            assert downloaded.content.startswith(b"PK")
    finally:
        main.app.dependency_overrides.clear()


def test_parallel_universal_conversions_are_isolated():
    context = ConversionContext(
        target_slicer="anycubic",
        target_printer_id="kobra_s1",
        nozzle_size_mm=0.4,
        material_id="pla",
    )

    def run():
        return convert_3mf(_core_3mf_bytes(), context, original_filename="parallel.3mf")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: run(), range(8)))

    assert len({item.conversion_id for item in results}) == 8
    assert len({item.output for item in results}) == 1
    assert all(item.output_filename == "parallel_AutoSlice.3mf" for item in results)
    assert all(item.report.compatibility_score == results[0].report.compatibility_score for item in results)
