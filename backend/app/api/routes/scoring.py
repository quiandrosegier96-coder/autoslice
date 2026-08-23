"""
AutoSlice — Scoring route.

GET /api/scoring/report/{job_id}
  Runs geometry analysis → risk scoring → settings decisions.
  Returns a full GenerationReport: features, risk scores, per-domain
  decisions with reasons, and (optionally) the engine trace + delta
  if the job has a completed conversion logged.
"""

import asyncio
import dataclasses
import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.ingestion.handler import find_owned_job
from app.ingestion.unpacker import unpack
from app.parser.model_parser import parse_model_files
from app.geometry.analyzer import analyze_mesh
from app.geometry.mesh_loader import merge_meshes
from app.scoring.models import GeometryFeatures, GenerationReport, DecisionEntry
from app.scoring.scorer import compute_risk_scores
from app.scoring.decisions import compute_settings_decisions
from app.scoring.printability import compute_printability
from app.explain.generator import generate_explanations
from app.orientation.scorer import score_orientations
from app.database import get_generation_trace

from datetime import datetime, timezone

router = APIRouter()


@router.get("/scoring/report/{job_id}", response_model=GenerationReport)
async def scoring_report(
    job_id: str, current_user: dict = Depends(get_current_user)
) -> GenerationReport:
    """
    Full scoring report for a previously uploaded 3MF file.

    Pipeline:
      1. Unpack + parse the archive (idempotent)
      2. Run geometry analysis
      3. Build GeometryFeatures (Pydantic bridge)
      4. Compute risk scores with reasons
      5. Compute settings decisions with reasons
      6. Merge engine trace + settings delta if a conversion exists

    The report is stateless — it can be called any number of times
    and will re-derive scores from the raw geometry each time.
    """
    job = find_owned_job(job_id, int(current_user["sub"]))
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    loop = asyncio.get_event_loop()

    archive = await loop.run_in_executor(None, unpack, job.archive_path, job.extract_dir)
    if not archive.model_files:
        raise HTTPException(status_code=422, detail="No model files found in archive.")

    try:
        parsed_model = await loop.run_in_executor(
            None, parse_model_files, archive.model_files, archive.object_type_map
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Parse failed: {exc}")

    if not parsed_model.objects:
        raise HTTPException(status_code=422, detail="No mesh objects found.")

    try:
        mesh = await loop.run_in_executor(None, merge_meshes, parsed_model.objects)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to load mesh: {exc}")

    try:
        geometry = await loop.run_in_executor(
            None, analyze_mesh, mesh, len(parsed_model.objects)
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Geometry analysis failed: {exc}")

    features     = GeometryFeatures.from_geometry_analysis(geometry)
    scores       = compute_risk_scores(features)
    decisions    = compute_settings_decisions(features, scores)
    printability = compute_printability(
        support_risk   = scores.support.value,
        adhesion_risk  = scores.adhesion.value,
        stability_risk = scores.stability.value,
        detail_risk    = scores.detail.value,
        bridge_risk    = scores.bridge.value,
    )
    explanations = generate_explanations(decisions, features, scores)

    try:
        orientation = await loop.run_in_executor(None, score_orientations, mesh)
    except Exception:
        from app.orientation.models import OrientationCandidate, OrientationReport
        _fb = OrientationCandidate(
            label="Original", rotation_euler_deg=[0, 0, 0],
            overhang_area_ratio=0.0, contact_area_mm2=0.0,
            height_to_base_ratio=0.0, height_mm=0.0,
            support_score=50, adhesion_score=50,
            stability_score=50, height_score=50, total_score=50,
        )
        orientation = OrientationReport(
            recommended=_fb, original=_fb, all_candidates=[_fb],
            improvement=0, should_rotate=False, support_reduction_pct=0.0,
            reasons=["Orientation analysis unavailable."],
        )

    # Pull engine trace + delta from the DB if a conversion was logged
    trace_data = get_generation_trace(job_id)
    decision_trace: list[DecisionEntry] = []
    settings_delta: dict = {}
    printer_id = "unknown"
    filament   = "unknown"
    nozzle_mm  = 0.4

    if trace_data:
        printer_id = trace_data.get("printer_id", printer_id)
        filament   = trace_data.get("filament", filament)
        nozzle_mm  = trace_data.get("nozzle_mm", nozzle_mm)
        settings_delta = trace_data.get("settings_delta", {})
        for entry in trace_data.get("decision_trace", []):
            decision_trace.append(DecisionEntry(**entry))

    return GenerationReport(
        job_id         = job_id,
        printer_id     = printer_id,
        filament       = filament,
        nozzle_mm      = nozzle_mm,
        geometry       = features,
        risk_scores    = scores,
        difficulty     = scores.difficulty,
        printability   = printability,
        explanations   = explanations,
        orientation    = orientation,
        decisions      = decisions,
        decision_trace = decision_trace,
        settings_delta = settings_delta,
        generated_at   = datetime.now(timezone.utc),
    )
