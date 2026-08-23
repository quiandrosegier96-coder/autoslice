"""Conservative slicer capability profiles; fixture-unverified claims stay limited."""

from app.threemf.capabilities.model import Capability, FeatureSupport, SlicerCapabilities
from app.threemf.domain.metadata import SlicerType

BAMBU_CAPABILITIES = SlicerCapabilities(SlicerType.BAMBU, (
    Capability("core_objects", FeatureSupport.SUPPORTED),
    Capability("components_and_transforms", FeatureSupport.SUPPORTED),
    Capability("print_settings", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Known project-setting keys are mapped."),
    Capability("materials_and_tools", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Explicit assignments are mapped; painting remains opaque."),
    Capability("object_specific_settings", FeatureSupport.PRESERVED_OPAQUE),
    Capability("multiple_plates", FeatureSupport.PRESERVED_OPAQUE),
    Capability("modifiers", FeatureSupport.SUPPORTED_WITH_LIMITS),
    Capability("support_painting", FeatureSupport.PRESERVED_OPAQUE),
    Capability("color_painting", FeatureSupport.PRESERVED_OPAQUE),
    Capability("variable_layer_height", FeatureSupport.SUPPORTED_WITH_LIMITS),
))


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

CURA_CAPABILITIES = SlicerCapabilities(SlicerType.CURA, (
    Capability("core_objects", FeatureSupport.SUPPORTED, notes="Core 3MF scene parsing is generic; real Cura verification is pending."),
    Capability("components_and_transforms", FeatureSupport.SUPPORTED, notes="Core transforms are preserved."),
    Capability("print_settings", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Only explicitly mapped Cura setting keys are semantic."),
    Capability("materials_and_tools", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Explicit object extruder numbers are separated from material identity."),
    Capability("object_specific_settings", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Recognized object metadata is attached to the object; all source parts remain opaque."),
    Capability("multiple_plates", FeatureSupport.PRESERVED_OPAQUE, notes="No real Cura multi-build fixture is available."),
    Capability("modifiers", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Known mesh roles are semantic; region targeting is fixture-unverified."),
    Capability("supports", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Known support flags and mesh roles are mapped."),
    Capability("color_painting", FeatureSupport.PRESERVED_OPAQUE),
    Capability("variable_layer_height", FeatureSupport.PRESERVED_OPAQUE),
))

CURA_TARGET_CAPABILITIES = SlicerCapabilities(SlicerType.CURA, ())

ANYCUBIC_TARGET_CAPABILITIES = SlicerCapabilities(SlicerType.ANYCUBIC, (
    Capability("core_objects", FeatureSupport.SUPPORTED),
    Capability("components_and_transforms", FeatureSupport.SUPPORTED),
    Capability("print_settings", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="AutoSlice emits the verified target-setting subset."),
    Capability("materials_and_tools", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="Only explicit material-to-tool assignments are emitted."),
    Capability("object_specific_settings", FeatureSupport.SUPPORTED_WITH_LIMITS),
    Capability("multiple_plates", FeatureSupport.UNSUPPORTED, notes="Multi-plate target behavior lacks a real fixture."),
    Capability("modifiers", FeatureSupport.UNSUPPORTED),
    Capability("support_painting", FeatureSupport.UNSUPPORTED),
    Capability("support_generation", FeatureSupport.SUPPORTED_WITH_LIMITS, notes="AutoSlice plans normal/tree support settings; no support mesh is embedded."),
    Capability("support_types", FeatureSupport.SUPPORTED_WITH_LIMITS, limits=(("types", "normal,tree"),)),
    Capability("support_blockers", FeatureSupport.PRESERVED_OPAQUE),
    Capability("support_enforcers", FeatureSupport.PRESERVED_OPAQUE),
    Capability("color_painting", FeatureSupport.UNSUPPORTED),
    Capability("variable_layer_height", FeatureSupport.UNSUPPORTED),
))


def capabilities_for(slicer: SlicerType) -> SlicerCapabilities:
    if slicer is SlicerType.BAMBU:
        return BAMBU_CAPABILITIES
    if slicer is SlicerType.ORCA:
        return ORCA_CAPABILITIES
    if slicer is SlicerType.PRUSA:
        return PRUSA_CAPABILITIES
    if slicer is SlicerType.CURA:
        return CURA_CAPABILITIES
    return SlicerCapabilities(slicer)


def target_capabilities_for(slicer: SlicerType) -> SlicerCapabilities:
    if slicer is SlicerType.ANYCUBIC:
        return ANYCUBIC_TARGET_CAPABILITIES
    if slicer is SlicerType.CURA:
        return CURA_TARGET_CAPABILITIES
    return SlicerCapabilities(slicer)
