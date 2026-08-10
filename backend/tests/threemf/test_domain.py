import pytest
from app.threemf.domain.build import Build, BuildItem
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import ModelObject, Transform
from app.threemf.domain.metadata import PackageInfo, SourceInfo


def test_transform_requires_twelve_values():
    with pytest.raises(ValueError, match="12 values"):
        Transform((1.0, 2.0))


def test_document_rejects_dangling_build_reference():
    with pytest.raises(ValueError, match="dangling"):
        Universal3MFDocument("1.0", SourceInfo(), PackageInfo("3D/model.model"), objects=(ModelObject("1"),), build=Build((BuildItem("2"),)))


def test_document_rejects_duplicate_object_identity():
    with pytest.raises(ValueError, match="unique"):
        Universal3MFDocument("1.0", SourceInfo(), PackageInfo("3D/model.model"), objects=(ModelObject("1"), ModelObject("1")))
