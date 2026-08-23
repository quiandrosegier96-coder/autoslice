"""
AutoSlice — Analyze route.
GET /api/analyze/{job_id}
  Runs the full analysis pipeline and returns a JSON report.
"""

import asyncio
import dataclasses
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.ingestion.handler import find_owned_job
from app.ingestion.unpacker import unpack
from app.parser.model_parser import parse_model_files
from app.parser.metadata_extractor import extract_archive_metadata, extract_source_filaments
from app.geometry.analyzer import analyze_mesh
from app.geometry.mesh_loader import merge_meshes
from app.support.detector import get_support_preview
from app.support.models import SupportPreviewData
from app.normalization.intent import normalize
from app.scoring.models import GeometryFeatures
from app.scoring.scorer import compute_risk_scores
from app.scoring.decisions import compute_settings_decisions
from app.scoring.printability import PrintabilityScore, compute_printability
from app.explain.models import ExplanationReport
from app.explain.generator import generate_explanations
from app.orientation.models import OrientationReport
from app.orientation.scorer import score_orientations
from app.geometry.nozzle_risk import assess_nozzle_risk
from app.auth.dependencies import get_current_user
from app.config import settings
from app.threemf.capabilities import capabilities_for
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.parsers import default_parser_registry

router = APIRouter()


# ---------- Response schemas ----------

class BoundingBoxSchema(BaseModel):
    x_mm: float
    y_mm: float
    z_mm: float
    volume_cm3: float


class OverhangSchema(BaseModel):
    has_overhangs: bool
    max_angle_deg: float
    overhang_area_ratio: float
    mild_area_ratio: float = 0.0
    moderate_area_ratio: float = 0.0
    severe_area_ratio: float = 0.0
    estimated_support_area_mm2: float = 0.0


class BridgeSchema(BaseModel):
    has_bridges: bool
    max_span_mm: float
    bridge_area_mm2: float = 0.0
    cluster_count: int = 0


class ThinWallSchema(BaseModel):
    has_thin_walls: bool
    min_thickness_mm: float


class GeometrySchema(BaseModel):
    bounding_box: BoundingBoxSchema
    part_count: int
    mesh_is_watertight: bool
    estimated_volume_cm3: float
    surface_area_mm2: float
    contact_area_mm2: float
    height_to_base_ratio: float
    slenderness_ratio: float = 0.0
    center_of_mass_z_ratio: float = 0.5
    overhang: OverhangSchema
    bridge: BridgeSchema
    thin_wall: ThinWallSchema


class IntentSchema(BaseModel):
    difficulty: str
    needs_supports: bool
    support_density_hint: str
    needs_brim: bool
    size_class: str
    has_fine_detail: bool
    is_structurally_risky: bool
    support_risk: int
    adhesion_risk: int
    stability_risk: int
    detail_risk: int


class ModelInfoSchema(BaseModel):
    part_count: int
    unit: str


class ArchiveInfoSchema(BaseModel):
    filename: str
    size_bytes: int
    has_model_file: bool
    has_thumbnail: bool
    file_listing: list[str]


class NozzleRiskItemSchema(BaseModel):
    type:           str
    severity:       str   # "low" | "medium" | "high"
    reason:         str
    recommendation: str


class NozzleRiskReportSchema(BaseModel):
    has_risks:            bool
    risks:                list[NozzleRiskItemSchema] = Field(default_factory=list)
    recommended_z_hop_mm: float = 0.0
    recommended_combing:  str   = "off"
    recommended_flow_pct: float = 100.0


class SourceFilamentSchema(BaseModel):
    colors: list[str] = Field(default_factory=list)
    types:  list[str] = Field(default_factory=list)
    count:  int       = 1


class DetectedSourceSchema(BaseModel):
    slicer: str
    version: str | None = None
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class UniversalProjectSchema(BaseModel):
    objects: int
    plates: int
    materials: int


class CapabilityItemSchema(BaseModel):
    feature: str
    support: str
    notes: str = ""


class AnalyzeResponse(BaseModel):
    job_id: str
    archive: ArchiveInfoSchema
    model: ModelInfoSchema
    geometry: GeometrySchema
    intent: IntentSchema
    printability: PrintabilityScore
    explanations: ExplanationReport
    orientation: OrientationReport
    nozzle_risk: NozzleRiskReportSchema
    source_filaments: SourceFilamentSchema = Field(default_factory=SourceFilamentSchema)
    source: DetectedSourceSchema
    project: UniversalProjectSchema
    capabilities: list[CapabilityItemSchema] = Field(default_factory=list)
    universal_warnings: list[str] = Field(default_factory=list)
    universal_engine_enabled: bool = False


# ---------- Route ----------

@router.get("/analyze/{job_id}", response_model=AnalyzeResponse)
async def analyze(job_id: str, current_user: dict = Depends(get_current_user)) -> AnalyzeResponse:
    """
    Full analysis pipeline for a previously uploaded 3MF file.

    Pipeline:
      1. Look up job by job_id
      2. Unpack archive (skips if already extracted)
      3. Parse 3D/3dmodel.model XML
      4. Run geometry analysis (bounding box, overhangs, bridges)
      5. Normalize to ModelIntent
      6. Return structured JSON
    """
    job = find_owned_job(job_id, int(current_user["sub"]))
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    loop = asyncio.get_event_loop()

    try:
        container = await loop.run_in_executor(None, ThreeMFContainer.from_path, job.archive_path)
        universal = await loop.run_in_executor(None, default_parser_registry().parse, container)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Universal3MF analysis failed: {exc}") from exc

    capability_profile = capabilities_for(universal.source.slicer)
    universal_warnings: list[str] = []
    if universal.source.confidence < settings.universal_3mf_min_confidence:
        universal_warnings.append("Could not confidently identify the source slicer.")

    # Unpack if not already done (idempotent — zipfile just overwrites)
    archive = await loop.run_in_executor(
        None, unpack, job.archive_path, job.extract_dir
    )

    if not archive.model_files:
        raise HTTPException(
            status_code=422,
            detail="No .model files found in archive. Is this a valid 3MF file?",
        )

    # Parse all model files (handles Bambu multi-file 3MF)
    try:
        parsed_model = await loop.run_in_executor(
            None, parse_model_files, archive.model_files, archive.object_type_map
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse 3MF model: {exc}")

    if not parsed_model.objects:
        file_names = [f.name for f in archive.model_files]
        raise HTTPException(
            status_code=422,
            detail=f"No mesh objects found. Scanned {len(archive.model_files)} file(s): {file_names}",
        )

    # Build mesh once — shared by geometry analysis and orientation scorer
    try:
        mesh = await loop.run_in_executor(
            None, merge_meshes, parsed_model.objects
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to load mesh: {exc}")

    # Geometry analysis (CPU-bound → thread pool)
    try:
        geometry = await loop.run_in_executor(
            None, analyze_mesh, mesh, len(parsed_model.objects)
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Geometry analysis failed: {exc}")

    # Orientation optimization (CPU-bound, runs on same mesh — no extra copy)
    try:
        orientation = await loop.run_in_executor(None, score_orientations, mesh)
    except Exception:
        # Non-fatal — orientation is a best-effort enhancement
        from app.orientation.models import OrientationCandidate
        _fallback = OrientationCandidate(
            label="Original", rotation_euler_deg=[0, 0, 0],
            overhang_area_ratio=0.0, contact_area_mm2=0.0,
            height_to_base_ratio=0.0, height_mm=0.0,
            support_score=50, adhesion_score=50,
            stability_score=50, height_score=50, total_score=50,
        )
        orientation = OrientationReport(
            recommended=_fallback, original=_fallback, all_candidates=[_fallback],
            improvement=0, should_rotate=False, support_reduction_pct=0.0,
            reasons=["Orientation analysis unavailable."],
        )

    # Normalize
    intent = normalize(geometry)

    # Scoring layer — builds full features + risk scores for printability + explanations
    features     = GeometryFeatures.from_geometry_analysis(geometry)
    risk_scores  = compute_risk_scores(features)
    decisions    = compute_settings_decisions(features, risk_scores)
    printability = compute_printability(
        support_risk   = risk_scores.support.value,
        adhesion_risk  = risk_scores.adhesion.value,
        stability_risk = risk_scores.stability.value,
        detail_risk    = risk_scores.detail.value,
        bridge_risk    = risk_scores.bridge.value,
    )
    explanations = generate_explanations(decisions, features, risk_scores)

    # Nozzle collision risk assessment
    nozzle_risk_raw = assess_nozzle_risk(
        overhang_area_ratio   = geometry.overhang.overhang_area_ratio,
        severe_overhang_ratio = geometry.overhang.severe_area_ratio,
        bridge_max_span_mm    = geometry.bridge.max_span_mm,
        height_to_base_ratio  = geometry.height_to_base_ratio,
        min_wall_mm           = geometry.thin_wall.min_thickness_mm,
        has_thin_walls        = geometry.thin_wall.has_thin_walls,
    )
    nozzle_risk = NozzleRiskReportSchema(
        has_risks            = nozzle_risk_raw.has_risks,
        risks                = [
            NozzleRiskItemSchema(
                type=r.type, severity=r.severity,
                reason=r.reason, recommendation=r.recommendation,
            )
            for r in nozzle_risk_raw.risks
        ],
        recommended_z_hop_mm = nozzle_risk_raw.recommended_z_hop_mm,
        recommended_combing  = nozzle_risk_raw.recommended_combing,
        recommended_flow_pct = nozzle_risk_raw.recommended_flow_pct,
    )

    # Archive metadata
    meta = extract_archive_metadata(
        original_filename=job.original_filename,
        size_bytes=job.size_bytes,
        extract_dir=job.extract_dir,
        all_files=archive.all_files,
    )
    source_filaments_raw = extract_source_filaments(job.extract_dir)

    return AnalyzeResponse(
        job_id=job_id,
        printability=printability,
        explanations=explanations,
        orientation=orientation,
        nozzle_risk=nozzle_risk,
        source_filaments=SourceFilamentSchema(
            colors=source_filaments_raw.colors,
            types=source_filaments_raw.types,
            count=source_filaments_raw.count,
        ),
        source=DetectedSourceSchema(
            slicer=universal.source.slicer.value,
            version=universal.source.version,
            confidence=universal.source.confidence,
            evidence=list(universal.source.detection_evidence),
        ),
        project=UniversalProjectSchema(
            objects=len(universal.objects), plates=len(universal.build.plates),
            materials=len(universal.materials),
        ),
        capabilities=[CapabilityItemSchema(
            feature=item.feature, support=item.support.value, notes=item.notes,
        ) for item in capability_profile.capabilities],
        universal_warnings=universal_warnings,
        universal_engine_enabled=settings.use_universal_3mf_engine,
        archive=ArchiveInfoSchema(
            filename=meta.original_filename,
            size_bytes=meta.size_bytes,
            has_model_file=meta.has_model_file,
            has_thumbnail=meta.has_thumbnail,
            file_listing=meta.all_file_paths,
        ),
        model=ModelInfoSchema(
            part_count=len(parsed_model.objects),
            unit=parsed_model.unit,
        ),
        geometry=GeometrySchema(
            bounding_box=BoundingBoxSchema(**dataclasses.asdict(geometry.bounding_box)),
            part_count=geometry.part_count,
            mesh_is_watertight=geometry.mesh_is_watertight,
            estimated_volume_cm3=geometry.estimated_volume_cm3,
            surface_area_mm2=geometry.surface_area_mm2,
            contact_area_mm2=geometry.contact_area_mm2,
            height_to_base_ratio=geometry.height_to_base_ratio,
            slenderness_ratio=geometry.slenderness_ratio,
            center_of_mass_z_ratio=geometry.center_of_mass_z_ratio,
            overhang=OverhangSchema(
                has_overhangs=geometry.overhang.has_overhangs,
                max_angle_deg=geometry.overhang.max_angle_deg,
                overhang_area_ratio=geometry.overhang.overhang_area_ratio,
                mild_area_ratio=geometry.overhang.mild_area_ratio,
                moderate_area_ratio=geometry.overhang.moderate_area_ratio,
                severe_area_ratio=geometry.overhang.severe_area_ratio,
                estimated_support_area_mm2=geometry.overhang.estimated_support_area_mm2,
            ),
            bridge=BridgeSchema(
                has_bridges=geometry.bridge.has_bridges,
                max_span_mm=geometry.bridge.max_span_mm,
                bridge_area_mm2=geometry.bridge.bridge_area_mm2,
                cluster_count=geometry.bridge.cluster_count,
            ),
            thin_wall=ThinWallSchema(**dataclasses.asdict(geometry.thin_wall)),
        ),
        intent=IntentSchema(
            difficulty=intent.difficulty,
            needs_supports=intent.needs_supports,
            support_density_hint=intent.support_density_hint,
            needs_brim=intent.needs_brim,
            size_class=intent.size_class,
            has_fine_detail=intent.has_fine_detail,
            is_structurally_risky=intent.is_structurally_risky,
            support_risk=intent.support_risk,
            adhesion_risk=intent.adhesion_risk,
            stability_risk=intent.stability_risk,
            detail_risk=intent.detail_risk,
        ),
    )


# ── DEBUG HARDCODE ── remove before release ───────────────────────────────────
_DEBUG_SUPPORT_HARDCODE = False   # ← set True to activate
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/analyze/{job_id}/support-preview", response_model=SupportPreviewData)
async def support_preview(job_id: str, debug: bool = False, current_user: dict = Depends(get_current_user)) -> SupportPreviewData:
    """
    Compute and return support visualization data for the uploaded model.
    Result is cached in-process after the first call.

    Positions are in 3MF coordinate space (Z-up, mm). The frontend applies
    the same -π/2 X rotation used by ThreeMFLoader, then subtracts model_center
    to align with the AutoCamera centering transform.

    Query params:
      debug=true  — attach SupportDebugLayers to the response (all overhang
                    positions, active/filtered cluster centroids).  Intended
                    for development; not needed in production.
    """
    # ── DEBUG: return one hardcoded support at a fixed world position ────────
    if _DEBUG_SUPPORT_HARDCODE:
        from app.support.models import SupportColumn, TreeBranch
        return SupportPreviewData(
            job_id             = job_id,
            needs_supports     = True,
            support_type       = "tree",
            placement          = "buildplate_only",
            overhang_positions = [],
            overhang_severity  = [],
            support_columns    = [],
            tree_branches      = [
                TreeBranch(
                    start     = [0.0, 0.0, 50.0],   # 3MF space: X=0, Y=0, Z=50mm
                    end       = [0.0, 0.0,  0.0],   # straight down to bed
                    radius    = 2.0,
                    is_tip    = True,
                    parent_id = None,
                    branch_id = 0,
                ),
            ],
            trunk_count   = 1,
            tip_count     = 1,
            model_center  = [0.0, 0.0, 25.0],
            model_floor_z = 0.0,
        )
    # ─────────────────────────────────────────────────────────────────────────

    job = find_owned_job(job_id, int(current_user["sub"]))
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    loop = asyncio.get_event_loop()

    archive = await loop.run_in_executor(None, unpack, job.archive_path, job.extract_dir)
    if not archive.model_files:
        raise HTTPException(status_code=422, detail="No .model files found in archive.")

    try:
        parsed_model = await loop.run_in_executor(
            None, parse_model_files, archive.model_files, archive.object_type_map
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse 3MF model: {exc}")

    try:
        mesh = await loop.run_in_executor(None, merge_meshes, parsed_model.objects)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to load mesh: {exc}")

    return await loop.run_in_executor(None, get_support_preview, job_id, mesh, debug)
