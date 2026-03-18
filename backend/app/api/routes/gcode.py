"""
AutoSlice — G-code validation route.

POST /api/gcode/validate
  Accepts raw G-code text, runs the validator, optionally returns a fixed copy.

The validator detects:
  - Relative vs absolute extrusion mode (M83 / M82)
  - Missing or insufficient G92 E0 extruder resets
  - Very high absolute E values (likely missing reset)
  - Absent extrusion mode declaration

When issues are fixable (M83 + missing G92 E0):
  - Inserts G92 E0 at every layer change
  - Marks status as "fixed"
  - Returns the corrected G-code in fixed_gcode

The endpoint accepts up to 10 MB of G-code text.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.gcode.validator import MAX_GCODE_BYTES, validate_gcode

router = APIRouter()


class GcodeValidateRequest(BaseModel):
    gcode: str


class GcodeValidateResponse(BaseModel):
    status: str                    # "ok" | "warning" | "fixed" | "error"
    has_m83: bool
    has_m82: bool
    g92_e0_count: int
    layer_count: int
    line_count: int
    issues: list[str]
    fixes_applied: list[str]
    fixed_gcode: str | None = None


@router.post("/gcode/validate", response_model=GcodeValidateResponse)
async def validate_gcode_endpoint(
    request: Request,
    body: GcodeValidateRequest,
) -> GcodeValidateResponse:
    """
    Validate G-code and optionally return a corrected version.

    Body
    ----
    gcode : str
        Raw G-code content as a single string (≤ 10 MB).

    Returns
    -------
    GcodeValidateResponse
        Validation report.  If ``status == "fixed"``, ``fixed_gcode`` contains
        the corrected G-code ready for download.
    """
    if len(body.gcode.encode()) > MAX_GCODE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"G-code payload exceeds the {MAX_GCODE_BYTES // 1_048_576} MB limit.",
        )

    if not body.gcode.strip():
        raise HTTPException(status_code=422, detail="G-code payload is empty.")

    result = validate_gcode(body.gcode)
    return GcodeValidateResponse(**asdict(result))
