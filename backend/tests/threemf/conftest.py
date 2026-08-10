from io import BytesIO
import zipfile

import pytest

MODEL_XML = b'''<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><metadata name="Title">Two objects</metadata><metadata name="Application">Bambu Studio</metadata><resources><basematerials id="5"><base name="Red PLA" displaycolor="#FF0000FF"/></basematerials><object id="1" name="Triangle" type="model" pid="5" pindex="0"><mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices><triangles><triangle v1="0" v2="1" v3="2" pid="5" p1="0"/></triangles></mesh></object><object id="2" name="Assembly" type="model"><components><component objectid="1" transform="1 0 0 0 1 0 0 0 1 10 0 0"/></components></object></resources><build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 20 0 0"/></build></model>'''
RELS_XML = b'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''


def make_3mf(extra: dict[str, bytes] | None = None, model_xml: bytes = MODEL_XML) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", RELS_XML)
        archive.writestr("3D/3dmodel.model", model_xml)
        for path, payload in (extra or {}).items():
            archive.writestr(path, payload)
    return output.getvalue()


@pytest.fixture
def core_3mf_bytes() -> bytes:
    return make_3mf()


@pytest.fixture
def three_mf_factory():
    return make_3mf
