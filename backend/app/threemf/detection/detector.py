"""Evidence-based slicer detection with explicit confidence."""

from dataclasses import dataclass
import json

from app.threemf.container.opc import primary_model_path
from app.threemf.container.security import UnsafeThreeMFError
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.container.xml import local_name, parse_xml
from app.threemf.domain.metadata import SlicerType


@dataclass(frozen=True)
class DetectionResult:
    slicer: SlicerType
    confidence: float
    evidence: tuple[str, ...] = ()
    version: str | None = None


def _config_keys(container: ThreeMFContainer) -> set[str]:
    path = "Metadata/project_settings.config"
    if not container.exists(path):
        return set()
    try:
        value = json.loads(container.read(path).decode("utf-8", errors="replace"))
        return set(value) if isinstance(value, dict) else set()
    except (ValueError, TypeError):
        return set()


def _cura_relationship_evidence(container: ThreeMFContainer) -> tuple[float, str] | None:
    if not container.exists("_rels/.rels"):
        return None
    root = parse_xml(container.read("_rels/.rels"), "_rels/.rels")
    for relationship in root:
        if relationship.attrib.get("TargetMode", "Internal").lower() == "external":
            raise UnsafeThreeMFError("External relationships cannot be used as Cura detection evidence.")
        relationship_type = relationship.attrib.get("Type", "").lower()
        target = relationship.attrib.get("Target", "").lower()
        if "ultimaker" in relationship_type or "cura" in relationship_type or "cura" in target:
            return 0.35, "Cura package relationship"
    return None


def detect_3mf(container: ThreeMFContainer) -> DetectionResult:
    evidence: dict[SlicerType, list[tuple[float, str]]] = {item: [] for item in SlicerType}
    paths = set(container.paths)
    keys = _config_keys(container)
    for path, slicer, weight in (
        ("Metadata/BambuStudio.config", SlicerType.BAMBU, 0.7),
        ("Metadata/AnycubicSlicer.config", SlicerType.ANYCUBIC, 0.85),
        ("Metadata/slice_info.config", SlicerType.ANYCUBIC, 0.25),
        ("Metadata/PrusaSlicer.config", SlicerType.PRUSA, 0.45),
        ("Metadata/Slic3r_PE.config", SlicerType.PRUSA, 0.45),
        ("Metadata/Cura.config", SlicerType.CURA, 0.45),
        ("Metadata/cura.xml", SlicerType.CURA, 0.45),
        ("Metadata/OrcaSlicer.config", SlicerType.ORCA, 0.8),
    ):
        if path in paths:
            evidence[slicer].append((weight, path))
    cura_relationship = _cura_relationship_evidence(container)
    if cura_relationship:
        evidence[SlicerType.CURA].append(cura_relationship)
    shared_project_keys = {"filament_colour", "filament_type", "printer_settings_id"} <= keys
    versions: dict[SlicerType, str] = {}
    try:
        model_path = primary_model_path(container)
        root = parse_xml(container.read(model_path), model_path)
        for child in root:
            if local_name(child.tag) != "metadata":
                continue
            value = (child.text or "").lower()
            name = child.attrib.get("name", "").lower()
            for token, slicer in (("bambu", SlicerType.BAMBU), ("orca", SlicerType.ORCA), ("prusa", SlicerType.PRUSA), ("anycubic", SlicerType.ANYCUBIC), ("cura", SlicerType.CURA)):
                if token in value or token in name:
                    evidence[slicer].append((0.45 if slicer in {SlicerType.PRUSA, SlicerType.CURA} else 0.55, f"model metadata: {token}"))
                    if child.text:
                        versions[slicer] = child.text.strip()
            if name == "slic3rpe:version3mf" and child.text:
                versions[SlicerType.PRUSA] = child.text.strip()
    except ValueError:
        return DetectionResult(SlicerType.UNKNOWN, 0.0, ("No valid primary model",))
    winner = max(evidence, key=lambda item: sum(weight for weight, _ in evidence[item]))
    score = min(0.99, sum(weight for weight, _ in evidence[winner]))
    if score == 0:
        return DetectionResult(SlicerType.CORE, 0.5, ("Valid core 3MF package",))
    reasons = [reason for _, reason in evidence[winner]]
    prusa_keys = {"perimeters", "top_solid_layers", "bottom_solid_layers", "fill_density", "fill_pattern"}
    if winner is SlicerType.PRUSA and len(prusa_keys & keys) >= 3:
        score = min(0.99, score + 0.2)
        reasons.append("Prusa print-settings keyset")
    if winner is SlicerType.PRUSA and len(reasons) < 2:
        return DetectionResult(SlicerType.UNKNOWN, score, tuple(reasons), versions.get(winner))
    if winner is SlicerType.CURA and len(reasons) < 2:
        return DetectionResult(SlicerType.UNKNOWN, score, tuple(reasons), versions.get(winner))
    if shared_project_keys and winner in {SlicerType.BAMBU, SlicerType.ORCA}:
        score = min(0.99, score + 0.1)
        reasons.append("Bambu/Orca project settings keyset")
    return DetectionResult(winner, score, tuple(reasons), versions.get(winner))
