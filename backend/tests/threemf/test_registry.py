from app.threemf.container.reader import ThreeMFContainer
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers import default_parser_registry


def test_default_registry_prefers_specific_adapter(three_mf_factory):
    payload = three_mf_factory({"Metadata/AnycubicSlicer.config": b"{}"})
    document = default_parser_registry().parse(ThreeMFContainer.from_bytes(payload))
    assert document.source.slicer is SlicerType.ANYCUBIC
