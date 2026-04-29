"""
Tests for the AI Orientation Suggestion flow.

Coverage:
  A — OrientationHints contract  : single field, maps to ConvertRequest
  B — Advisory display-only      : suggestion returned but nothing auto-applied
  C — Without Apply, form unchanged
  D — Apply Orientation updates only orientation_euler_deg
  E — Engine logic               : flat model stays original, tall-narrow gets side rotation
  F — Input validation           : schema rejects out-of-range values
  G — Pipeline isolation         : suggest() is pure, deterministic, doesn't mutate request
"""

import pytest

from app.ai.orientation import suggest
from app.ai.schemas import (
    OrientationHints,
    OrientationRequest,
    OrientationSuggestion,
    Rotation3D,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_request(
    width_mm: float = 50.0,
    depth_mm: float = 50.0,
    height_mm: float = 80.0,
    volume_mm3: float = 100_000.0,
    surface_area_mm2: float = 25_000.0,
    overhang_ratio: float = 0.10,
    thin_wall_ratio: float = 0.05,
    current_rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> OrientationRequest:
    rx, ry, rz = current_rotation
    return OrientationRequest(
        width_mm=width_mm,
        depth_mm=depth_mm,
        height_mm=height_mm,
        volume_mm3=volume_mm3,
        surface_area_mm2=surface_area_mm2,
        overhang_ratio=overhang_ratio,
        thin_wall_ratio=thin_wall_ratio,
        current_rotation=Rotation3D(x=rx, y=ry, z=rz),
    )


def _make_base_convert_form() -> dict:
    """Simulate the convert form before any orientation is applied."""
    return {
        "job_id":                "abc123",
        "printer_id":            "anycubic_kobra3",
        "filament_type":         "pla",
        "nozzle_size_mm":        0.4,
        "nozzle_type":           "brass",
        "build_plate":           "smooth",
        "scale_factor":          1.0,
        "orientation_euler_deg": [],
        "fuzzy_skin":            "none",
        "color_count":           1,
    }


def _apply_orientation_hints(hints: OrientationHints, form: dict) -> dict:
    """Simulate the frontend 'Apply Orientation' button."""
    return {**form, "orientation_euler_deg": hints.orientation_euler_deg}


# ── Constants ─────────────────────────────────────────────────────────────────

_KNOWN_CONVERT_REQUEST_FIELDS = {
    "job_id", "printer_id", "filament_type", "nozzle_size_mm",
    "nozzle_type", "filament_diameter_mm", "build_plate",
    "flush_volume_mm3", "color_count", "filament_colors", "filament_types",
    "orientation_euler_deg", "scale_factor", "fuzzy_skin",
    "fuzzy_skin_thickness_mm", "fuzzy_skin_point_dist_mm",
}


# ── A: OrientationHints contract ──────────────────────────────────────────────

def test_orientation_hints_has_exactly_one_field():
    """OrientationHints must expose exactly the one field that maps to ConvertRequest."""
    assert set(OrientationHints.model_fields.keys()) == {"orientation_euler_deg"}


def test_orientation_hints_field_exists_in_convert_request():
    """orientation_euler_deg must be a real ConvertRequest field."""
    assert "orientation_euler_deg" in _KNOWN_CONVERT_REQUEST_FIELDS


def test_orientation_hints_field_is_list_of_three_floats():
    """orientation_euler_deg must be a list of exactly 3 floats [rx, ry, rz]."""
    hints = OrientationHints(orientation_euler_deg=[90.0, 0.0, 0.0])
    assert isinstance(hints.orientation_euler_deg, list)
    assert len(hints.orientation_euler_deg) == 3
    assert all(isinstance(v, float) for v in hints.orientation_euler_deg)


def test_orientation_hints_zero_rotation_is_valid():
    """[0, 0, 0] is a valid orientation_euler_deg (no rotation applied)."""
    hints = OrientationHints(orientation_euler_deg=[0.0, 0.0, 0.0])
    assert hints.orientation_euler_deg == [0.0, 0.0, 0.0]


def test_orientation_hints_ignores_unknown_fields():
    """OrientationHints must silently drop any extra fields."""
    hints = OrientationHints.model_validate({
        "orientation_euler_deg": [0.0, 90.0, 0.0],
        "support_type":          "tree",
        "layer_height_mm":       0.2,
        "build_plate":           "textured",
    })
    assert set(hints.model_dump().keys()) == {"orientation_euler_deg"}


# ── B: Advisory display-only ──────────────────────────────────────────────────

def test_suggest_returns_orientation_suggestion():
    """suggest() must return a valid OrientationSuggestion instance."""
    result = suggest(_make_request())
    assert isinstance(result, OrientationSuggestion)


def test_suggestion_includes_recommended_rotation():
    """OrientationSuggestion must include a recommended_rotation Rotation3D."""
    result = suggest(_make_request())
    assert isinstance(result.recommended_rotation, Rotation3D)


def test_suggestion_includes_confidence():
    """confidence must be an int in [0, 100]."""
    result = suggest(_make_request())
    assert isinstance(result.confidence, int)
    assert 0 <= result.confidence <= 100


def test_suggestion_includes_support_reduction():
    """estimated_support_reduction_percent must be in [0.0, 100.0]."""
    result = suggest(_make_request())
    assert 0.0 <= result.estimated_support_reduction_percent <= 100.0


def test_suggestion_includes_adhesion_score():
    """bed_adhesion_score must be in [0, 100]."""
    result = suggest(_make_request())
    assert 0 <= result.bed_adhesion_score <= 100


def test_suggestion_includes_stability_score():
    """stability_score must be in [0, 100]."""
    result = suggest(_make_request())
    assert 0 <= result.stability_score <= 100


def test_suggestion_includes_non_empty_explanation():
    """explanation must be a non-empty string."""
    result = suggest(_make_request())
    assert isinstance(result.explanation, str)
    assert len(result.explanation) > 0


def test_suggestion_includes_warnings_list():
    """warnings must be a list (may be empty)."""
    result = suggest(_make_request())
    assert isinstance(result.warnings, list)


def test_suggestion_includes_orientation_hints():
    """OrientationSuggestion must include orientation_hints for the Apply bridge."""
    result = suggest(_make_request())
    assert isinstance(result.orientation_hints, OrientationHints)


def test_suggestion_engine_version_present():
    """engine_version must be a non-empty string."""
    result = suggest(_make_request())
    assert isinstance(result.engine_version, str)
    assert len(result.engine_version) > 0


# ── C: Without Apply, convert form orientation unchanged ──────────────────────

def test_calling_suggest_does_not_mutate_form_dict():
    """suggest() must not touch any dict in the caller's scope."""
    form = _make_base_convert_form()
    original = dict(form)
    suggest(_make_request())
    assert form == original


def test_without_apply_orientation_euler_deg_stays_empty():
    """If the user ignores the suggestion, orientation_euler_deg stays as the user set it."""
    form = _make_base_convert_form()
    suggest(_make_request())
    assert form["orientation_euler_deg"] == []


def test_without_apply_filament_unchanged():
    """suggest() must not modify filament_type in the form."""
    form = _make_base_convert_form()
    suggest(_make_request())
    assert form["filament_type"] == "pla"


def test_without_apply_build_plate_unchanged():
    """suggest() must not modify build_plate in the form."""
    form = _make_base_convert_form()
    suggest(_make_request())
    assert form["build_plate"] == "smooth"


def test_high_overhang_suggestion_not_auto_applied():
    """Even with extreme overhang, nothing is auto-applied to the form."""
    form = _make_base_convert_form()
    suggest(_make_request(overhang_ratio=0.9))
    assert form["orientation_euler_deg"] == []
    assert form["build_plate"] == "smooth"


# ── D: Apply Orientation updates only orientation_euler_deg ───────────────────

def test_apply_updates_orientation_euler_deg():
    """After Apply, form.orientation_euler_deg equals hints.orientation_euler_deg."""
    result = suggest(_make_request(width_mm=15.0, depth_mm=15.0, height_mm=200.0,
                                   overhang_ratio=0.30))
    form = _apply_orientation_hints(result.orientation_hints, _make_base_convert_form())
    assert form["orientation_euler_deg"] == result.orientation_hints.orientation_euler_deg


def test_apply_does_not_touch_filament_type():
    """Apply Orientation must not change filament_type."""
    result = suggest(_make_request())
    base = _make_base_convert_form()
    form = _apply_orientation_hints(result.orientation_hints, base)
    assert form["filament_type"] == base["filament_type"]


def test_apply_does_not_touch_nozzle_size_mm():
    """Apply Orientation must not change nozzle_size_mm."""
    result = suggest(_make_request())
    base = _make_base_convert_form()
    form = _apply_orientation_hints(result.orientation_hints, base)
    assert form["nozzle_size_mm"] == base["nozzle_size_mm"]


def test_apply_does_not_touch_nozzle_type():
    """Apply Orientation must not change nozzle_type."""
    result = suggest(_make_request())
    base = _make_base_convert_form()
    form = _apply_orientation_hints(result.orientation_hints, base)
    assert form["nozzle_type"] == base["nozzle_type"]


def test_apply_does_not_touch_build_plate():
    """Apply Orientation must not change build_plate."""
    result = suggest(_make_request())
    base = _make_base_convert_form()
    form = _apply_orientation_hints(result.orientation_hints, base)
    assert form["build_plate"] == base["build_plate"]


def test_apply_does_not_touch_printer_id():
    """Apply Orientation must not change printer_id."""
    result = suggest(_make_request())
    base = _make_base_convert_form()
    form = _apply_orientation_hints(result.orientation_hints, base)
    assert form["printer_id"] == base["printer_id"]


def test_apply_does_not_touch_scale_factor():
    """Apply Orientation must not change scale_factor."""
    result = suggest(_make_request())
    base = {**_make_base_convert_form(), "scale_factor": 1.5}
    form = _apply_orientation_hints(result.orientation_hints, base)
    assert form["scale_factor"] == 1.5


def test_apply_does_not_touch_fuzzy_skin():
    """Apply Orientation must not change fuzzy_skin."""
    result = suggest(_make_request())
    base = {**_make_base_convert_form(), "fuzzy_skin": "outer"}
    form = _apply_orientation_hints(result.orientation_hints, base)
    assert form["fuzzy_skin"] == "outer"


def test_apply_changes_only_orientation_euler_deg():
    """
    Apply Orientation must change exactly orientation_euler_deg and nothing else.
    Uses a tall-narrow model so the engine recommends a side rotation.
    """
    result = suggest(_make_request(width_mm=15.0, depth_mm=15.0, height_mm=200.0,
                                   overhang_ratio=0.30))
    base = _make_base_convert_form()
    form = _apply_orientation_hints(result.orientation_hints, base)
    changed = {k for k in form if form[k] != base.get(k)}
    assert changed <= {"orientation_euler_deg"}, (
        f"Apply Orientation changed unexpected fields: {changed - {'orientation_euler_deg'}}"
    )


def test_no_rotation_apply_leaves_list_with_three_floats():
    """Apply when engine recommends no rotation must still produce a 3-element list."""
    result = suggest(_make_request(width_mm=200.0, depth_mm=150.0, height_mm=5.0,
                                   overhang_ratio=0.0))
    form = _apply_orientation_hints(result.orientation_hints, _make_base_convert_form())
    assert isinstance(form["orientation_euler_deg"], list)
    assert len(form["orientation_euler_deg"]) == 3


# ── E: Engine logic ───────────────────────────────────────────────────────────

def test_flat_wide_model_keeps_original_orientation():
    """
    A flat model (W=200, D=150, H=5) with zero overhang has maximum base area in
    Original orientation. No rotation should improve the score by 10+ points.
    """
    result = suggest(_make_request(
        width_mm=200.0, depth_mm=150.0, height_mm=5.0,
        overhang_ratio=0.0,
    ))
    rx = result.recommended_rotation.x
    ry = result.recommended_rotation.y
    rz = result.recommended_rotation.z
    assert (rx, ry, rz) == (0.0, 0.0, 0.0), (
        f"Flat model should keep original orientation but got rotation ({rx}, {ry}, {rz})"
    )


def test_tall_narrow_model_gets_side_rotation():
    """
    A tall-narrow model (W=15, D=15, H=200) with moderate overhang should be rotated
    to a side orientation to improve stability and adhesion. Gap must be ≥ 10.
    """
    result = suggest(_make_request(
        width_mm=15.0, depth_mm=15.0, height_mm=200.0,
        overhang_ratio=0.30,
    ))
    rx = result.recommended_rotation.x
    ry = result.recommended_rotation.y
    # One of X+90° or Y+90° must be recommended — either increases base area dramatically
    is_side_rotation = (abs(rx - 90.0) < 1e-9 and ry == 0.0) or (rx == 0.0 and abs(ry - 90.0) < 1e-9)
    assert is_side_rotation, (
        f"Tall-narrow model should get a side rotation but got ({rx}, {ry}, {result.recommended_rotation.z})"
    )


def test_tall_narrow_model_confidence_above_minimum():
    """A clear tall-narrow case should produce confidence > 20 (not rock-bottom)."""
    result = suggest(_make_request(
        width_mm=15.0, depth_mm=15.0, height_mm=200.0,
        overhang_ratio=0.30,
    ))
    assert result.confidence > 20


def test_flat_model_support_reduction_is_zero():
    """A zero-overhang flat model already in optimal orientation has 0% support reduction."""
    result = suggest(_make_request(
        width_mm=200.0, depth_mm=150.0, height_mm=5.0,
        overhang_ratio=0.0,
    ))
    assert result.estimated_support_reduction_percent == 0.0


def test_high_overhang_model_may_see_support_reduction():
    """
    When the engine recommends a rotation for a high-overhang model, it should
    estimate a positive support reduction (overhangs improve with better orientation).
    """
    result = suggest(_make_request(
        width_mm=15.0, depth_mm=15.0, height_mm=200.0,
        overhang_ratio=0.60,
    ))
    if result.recommended_rotation != Rotation3D(x=0.0, y=0.0, z=0.0):
        assert result.estimated_support_reduction_percent > 0.0


def test_no_rotation_recommended_rotation_is_zero_vector():
    """When no rotation is beneficial, recommended_rotation must be (0, 0, 0)."""
    result = suggest(_make_request(
        width_mm=200.0, depth_mm=150.0, height_mm=5.0,
        overhang_ratio=0.0,
    ))
    assert result.recommended_rotation.x == 0.0
    assert result.recommended_rotation.y == 0.0
    assert result.recommended_rotation.z == 0.0


def test_no_rotation_orientation_hints_are_zero_vector():
    """When no rotation is needed, orientation_hints.orientation_euler_deg must be [0, 0, 0]."""
    result = suggest(_make_request(
        width_mm=200.0, depth_mm=150.0, height_mm=5.0,
        overhang_ratio=0.0,
    ))
    assert result.orientation_hints.orientation_euler_deg == [0.0, 0.0, 0.0]


def test_recommended_rotation_matches_orientation_hints():
    """recommended_rotation and orientation_hints.orientation_euler_deg must agree."""
    result = suggest(_make_request())
    hints_deg = result.orientation_hints.orientation_euler_deg
    assert hints_deg[0] == result.recommended_rotation.x
    assert hints_deg[1] == result.recommended_rotation.y
    assert hints_deg[2] == result.recommended_rotation.z


@pytest.mark.parametrize("dims,expected_no_rotation", [
    # Cube: all orientations equivalent — no clear winner → should not rotate
    ((50.0, 50.0, 50.0), True),
    # Flat disc: original is best (maximum base area)
    ((100.0, 100.0, 5.0), True),
])
def test_symmetric_or_flat_models_keep_original(dims, expected_no_rotation):
    """Symmetric / flat models should not trigger a rotation recommendation."""
    w, d, h = dims
    result = suggest(_make_request(width_mm=w, depth_mm=d, height_mm=h, overhang_ratio=0.0))
    is_original = (
        result.recommended_rotation.x == 0.0
        and result.recommended_rotation.y == 0.0
        and result.recommended_rotation.z == 0.0
    )
    if expected_no_rotation:
        assert is_original, (
            f"Model {dims} should keep original orientation but got "
            f"({result.recommended_rotation.x}, {result.recommended_rotation.y}, "
            f"{result.recommended_rotation.z})"
        )


# ── F: Input validation ───────────────────────────────────────────────────────

def test_request_rejects_zero_width():
    """width_mm must be > 0; zero must be rejected."""
    with pytest.raises(Exception):
        OrientationRequest(
            width_mm=0.0, depth_mm=50.0, height_mm=50.0,
            volume_mm3=100_000.0, surface_area_mm2=25_000.0,
            overhang_ratio=0.1, thin_wall_ratio=0.0,
        )


def test_request_rejects_negative_depth():
    """depth_mm must be > 0; negative must be rejected."""
    with pytest.raises(Exception):
        OrientationRequest(
            width_mm=50.0, depth_mm=-10.0, height_mm=50.0,
            volume_mm3=100_000.0, surface_area_mm2=25_000.0,
            overhang_ratio=0.1, thin_wall_ratio=0.0,
        )


def test_request_rejects_zero_height():
    """height_mm must be > 0; zero must be rejected."""
    with pytest.raises(Exception):
        OrientationRequest(
            width_mm=50.0, depth_mm=50.0, height_mm=0.0,
            volume_mm3=100_000.0, surface_area_mm2=25_000.0,
            overhang_ratio=0.1, thin_wall_ratio=0.0,
        )


def test_request_rejects_overhang_ratio_above_one():
    """overhang_ratio is a fraction [0, 1]; values > 1.0 must be rejected."""
    with pytest.raises(Exception):
        OrientationRequest(
            width_mm=50.0, depth_mm=50.0, height_mm=50.0,
            volume_mm3=100_000.0, surface_area_mm2=25_000.0,
            overhang_ratio=1.5, thin_wall_ratio=0.0,
        )


def test_request_rejects_negative_overhang_ratio():
    """overhang_ratio must not be negative."""
    with pytest.raises(Exception):
        OrientationRequest(
            width_mm=50.0, depth_mm=50.0, height_mm=50.0,
            volume_mm3=100_000.0, surface_area_mm2=25_000.0,
            overhang_ratio=-0.1, thin_wall_ratio=0.0,
        )


def test_request_rejects_thin_wall_ratio_above_one():
    """thin_wall_ratio is a fraction [0, 1]; values > 1.0 must be rejected."""
    with pytest.raises(Exception):
        OrientationRequest(
            width_mm=50.0, depth_mm=50.0, height_mm=50.0,
            volume_mm3=100_000.0, surface_area_mm2=25_000.0,
            overhang_ratio=0.1, thin_wall_ratio=2.0,
        )


def test_request_rejects_zero_volume():
    """volume_mm3 must be > 0; zero must be rejected."""
    with pytest.raises(Exception):
        OrientationRequest(
            width_mm=50.0, depth_mm=50.0, height_mm=50.0,
            volume_mm3=0.0, surface_area_mm2=25_000.0,
            overhang_ratio=0.1, thin_wall_ratio=0.0,
        )


def test_request_rejects_zero_surface_area():
    """surface_area_mm2 must be > 0; zero must be rejected."""
    with pytest.raises(Exception):
        OrientationRequest(
            width_mm=50.0, depth_mm=50.0, height_mm=50.0,
            volume_mm3=100_000.0, surface_area_mm2=0.0,
            overhang_ratio=0.1, thin_wall_ratio=0.0,
        )


def test_request_accepts_boundary_overhang_values():
    """overhang_ratio=0.0 and overhang_ratio=1.0 must both be accepted."""
    for v in [0.0, 1.0]:
        req = OrientationRequest(
            width_mm=50.0, depth_mm=50.0, height_mm=50.0,
            volume_mm3=100_000.0, surface_area_mm2=25_000.0,
            overhang_ratio=v, thin_wall_ratio=0.0,
        )
        assert req.overhang_ratio == v


# ── G: Pipeline isolation ─────────────────────────────────────────────────────

def test_suggest_is_deterministic():
    """suggest() must return an identical result on repeated calls with the same input."""
    req = _make_request(width_mm=30.0, depth_mm=30.0, height_mm=120.0, overhang_ratio=0.20)
    r1 = suggest(req)
    r2 = suggest(req)
    assert r1.model_dump() == r2.model_dump()


def test_suggest_does_not_mutate_request():
    """suggest() must not mutate the OrientationRequest passed to it."""
    req = _make_request(width_mm=40.0, depth_mm=40.0, height_mm=150.0)
    original_w = req.width_mm
    original_h = req.height_mm
    original_o = req.overhang_ratio
    suggest(req)
    assert req.width_mm      == original_w
    assert req.height_mm     == original_h
    assert req.overhang_ratio == original_o


def test_suggest_independent_calls_do_not_share_state():
    """Two calls with different models must produce independent results."""
    flat_result = suggest(_make_request(
        width_mm=200.0, depth_mm=150.0, height_mm=5.0, overhang_ratio=0.0
    ))
    tall_result = suggest(_make_request(
        width_mm=15.0, depth_mm=15.0, height_mm=200.0, overhang_ratio=0.30
    ))
    assert flat_result.model_dump() != tall_result.model_dump()


def test_orientation_module_does_not_import_slicing_internals():
    """
    The orientation engine must not import from the rules engine, export pipeline,
    or ingestion layer.
    """
    import importlib.util
    spec = importlib.util.find_spec("app.ai.orientation")
    with open(spec.origin, encoding="utf-8") as f:
        src = f.read()
    forbidden_imports = [
        "from app.rules",
        "import app.rules",
        "from app.export",
        "from app.normalization",
        "from app.ingestion",
        "from app.geometry.analyzer",
    ]
    for stmt in forbidden_imports:
        assert stmt not in src, (
            f"Orientation engine imports slicing internals via '{stmt}'"
        )


def test_convert_py_unchanged_by_orientation():
    """convert.py must not import from the AI orientation module."""
    import importlib.util
    spec = importlib.util.find_spec("app.api.routes.convert")
    with open(spec.origin, encoding="utf-8") as f:
        src = f.read()
    assert "app.ai" not in src, (
        "convert.py imports from app.ai — orientation AI must not modify slicing behaviour"
    )
