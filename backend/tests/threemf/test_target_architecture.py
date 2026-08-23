import pytest

from app.threemf.capabilities import FeatureSupport, target_capabilities_for
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.conversion import ConversionError, ConversionErrorCode, create_conversion_service
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext, ConversionMode
from app.threemf.exporters import default_exporter_registry
from app.threemf.parsers.bambu import BambuParser
from app.threemf.translation.plan import build_translation_plan
from app.threemf.translation.engine import AutoSliceTranslationEngine
from app.threemf.validation import default_target_validator_registry


def test_default_registry_exposes_only_verified_anycubic_target():
    registry = default_exporter_registry()
    assert registry.get_exporter(SlicerType.ANYCUBIC)
    with pytest.raises(ValueError, match="No exporter"):
        registry.get_exporter(SlicerType.ORCA)
    with pytest.raises(ValueError, match="No exporter"):
        registry.get_exporter(SlicerType.PRUSA)


def test_translation_plan_compares_source_and_target_capabilities(three_mf_factory):
    payload = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    document = BambuParser().parse(ThreeMFContainer.from_bytes(payload))
    plan = build_translation_plan(document, SlicerType.ANYCUBIC)
    assert plan.source is SlicerType.BAMBU
    assert plan.target is SlicerType.ANYCUBIC
    assert plan.operations
    assert any(item.feature == "multiple_plates" for item in plan.operations)


def test_target_capabilities_do_not_claim_unimplemented_targets():
    assert target_capabilities_for(SlicerType.ANYCUBIC).for_feature("core_objects").support is FeatureSupport.SUPPORTED
    assert target_capabilities_for(SlicerType.ORCA).capabilities == ()
    assert target_capabilities_for(SlicerType.PRUSA).capabilities == ()


def test_target_validator_rejects_wrong_target_identity(three_mf_factory):
    bambu = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    with pytest.raises(ValueError, match="not an identifiable Anycubic"):
        default_target_validator_registry().validate(SlicerType.ANYCUBIC, bambu)


def test_conversion_rejects_unregistered_target_before_export(three_mf_factory):
    source = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    service = create_conversion_service()
    with pytest.raises(ConversionError) as caught:
        service.convert_3mf(source, ConversionContext("orca", target_printer_id="kobra_s1", material_id="pla"))
    assert caught.value.code is ConversionErrorCode.UNSUPPORTED_SLICER


def test_preserve_mode_skips_autoslice_optimization(three_mf_factory):
    source = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    document = BambuParser().parse(ThreeMFContainer.from_bytes(source))
    outcome = AutoSliceTranslationEngine().translate(
        document, ConversionContext("anycubic", target_printer_id="kobra_s1", mode=ConversionMode.PRESERVE),
    )
    assert outcome.document is document
    assert outcome.plan is not None
