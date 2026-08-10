import pytest
from app.threemf.container.opc import primary_model_path
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.validation import validate_3mf


def test_primary_model_relationship_resolves(core_3mf_bytes):
    assert primary_model_path(ThreeMFContainer.from_bytes(core_3mf_bytes)) == "3D/3dmodel.model"


def test_missing_primary_model_is_rejected():
    with pytest.raises(ValueError, match="primary model"):
        primary_model_path(ThreeMFContainer({"[Content_Types].xml": b"<Types/>"}))


def test_synthetic_complete_package_validates(core_3mf_bytes):
    result = validate_3mf(core_3mf_bytes)
    assert result.valid, result.diagnostics


def test_missing_content_types_fails_validation(three_mf_factory):
    container = ThreeMFContainer.from_bytes(three_mf_factory())
    entries = {path: container.read(path) for path in container.paths if path != "[Content_Types].xml"}
    result = validate_3mf(ThreeMFContainer(entries))
    assert not result.valid
    assert any(item.code == "package.content_types_missing" for item in result.diagnostics)
