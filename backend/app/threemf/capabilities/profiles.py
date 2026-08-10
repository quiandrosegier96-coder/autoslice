"""Conservative slicer capability profiles; fixture-unverified claims stay limited."""

from app.threemf.capabilities.model import Capability, FeatureSupport, SlicerCapabilities
from app.threemf.domain.metadata import SlicerType


ORCA_CAPABILITIES = SlicerCapabilities(SlicerType.ORCA, (
    Capability("core_objects", FeatureSupport.SUPPORTED, notes="Core 3MF objects are handled generically; real Orca fixture verification is pending."),
    Capability("components_and_transforms", FeatureSupport.SUPPORTED, notes="Core component/build transforms are preserved; Production Extension verification is pending."),
    Capability("print_settings", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Only the shared, explicitly mapped PrusaSlicer-family key subset is semantic."),
    Capability("materials_and_tools", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Filament arrays and explicit object extruder mappings are understood; painting is not."),
    Capability("object_specific_settings", FeatureSupport.PRESERVED_OPAQUE, notes="Unknown object settings remain in source config payloads."),
    Capability("multiple_plates", FeatureSupport.PRESERVED_OPAQUE, notes="No real multi-plate Orca fixture is available."),
    Capability("modifiers", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Known generic roles are retained; Orca targeting metadata is fixture-unverified."),
    Capability("support_painting", FeatureSupport.PRESERVED_OPAQUE, notes="No real painted-support fixture is available."),
    Capability("color_painting", FeatureSupport.PRESERVED_OPAQUE, notes="No real multicolor Orca fixture is available."),
    Capability("variable_layer_height", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="The known project flag is semantic; detailed layer profile data is opaque."),
))

PRUSA_CAPABILITIES = SlicerCapabilities(SlicerType.PRUSA, (
    Capability("core_objects", FeatureSupport.SUPPORTED, notes="Core 3MF objects are parsed generically; real Prusa fixture verification is pending."),
    Capability("components_and_transforms", FeatureSupport.SUPPORTED, notes="Core component and build transforms are preserved."),
    Capability("print_settings", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Known Prusa settings are mapped semantically; unknown keys remain opaque."),
    Capability("materials_and_tools", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Known filament arrays and explicit extruder assignments are mapped; real MMU verification is pending."),
    Capability("object_specific_settings", FeatureSupport.PRESERVED_OPAQUE, notes="Unmapped object settings remain in source payloads."),
    Capability("multiple_plates", FeatureSupport.PRESERVED_OPAQUE, notes="No real Prusa multi-plate fixture is available."),
    Capability("modifiers", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Generic modifier roles are retained; targeting requires fixture verification."),
    Capability("support_painting", FeatureSupport.PRESERVED_OPAQUE, notes="No real painted-support Prusa fixture is available."),
    Capability("color_painting", FeatureSupport.PRESERVED_OPAQUE, notes="No real MMU painting fixture is available."),
    Capability("variable_layer_height", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Known flags are semantic; detailed profiles remain opaque."),
))


def capabilities_for(slicer: SlicerType) -> SlicerCapabilities:
    if slicer is SlicerType.ORCA:
        return ORCA_CAPABILITIES
    if slicer is SlicerType.PRUSA:
        return PRUSA_CAPABILITIES
    return SlicerCapabilities(slicer)
