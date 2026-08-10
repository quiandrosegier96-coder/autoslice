"""Evidence-based slicer detection with explicit confidence."""

from dataclasses import dataclass
import json

from app.threemf.container.opc import primary_model_path
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
        ("Metadata/Cura.config", SlicerType.CURA, 0.8),
        ("Metadata/OrcaSlicer.config", SlicerType.ORCA, 0.8),
    ):
        if path in paths:
            evidence[slicer].append((weight, path))
    shared_project_keys = {"filament_colour", "filament_type", "printer_settings_id"} <= keys
    detected_version: str | None = None
    try:
        model_path = primary_model_path(container)
        root = parse_xml(container.read(model_path), model_path)
        for child in root:
            if local_name(child.tag) != "metadata":
                continue
            value = (child.text or "").lower()
            name = child.attrib.get("name", "").lower()
            if name in {"application", "slic3rpe:version3mf"} and child.text:
                detected_version = child.text.strip()
            for token, slicer in (("bambu", SlicerType.BAMBU), ("orca", SlicerType.ORCA), ("prusa", SlicerType.PRUSA), ("anycubic", SlicerType.ANYCUBIC), ("cura", SlicerType.CURA)):
                if token in value or token in name:
                    evidence[slicer].append((0.55 if slicer is not SlicerType.PRUSA else 0.45, f"model metadata: {token}"))
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
        return DetectionResult(SlicerType.UNKNOWN, score, tuple(reasons), detected_version)
    if shared_project_keys and winner in {SlicerType.BAMBU, SlicerType.ORCA}:
        score = min(0.99, score + 0.1)
        reasons.append("Bambu/Orca project settings keyset")
    return DetectionResult(winner, score, tuple(reasons), detected_version)
