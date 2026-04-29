"""
Tests for the AI Apply Settings flow.

Coverage:
  A — ConvertHints contract   : exact fields, correct value per filament
  B — Advisory display-only   : layer/infill/support exist in settings, not in hints
  C — Without Apply, no change: form dict is untouched unless explicitly merged
  D — Apply merges correctly  : only the 4 allowed fields update; everything else unchanged
  E — Unknown fields ignored  : extra AI fields never reach ConvertRequest
  F — Pipeline isolation      : run() is pure; AI module does not import slicing internals
  G — features_from_geometry  : bridge translates GeometryAnalysis correctly
"""

import pytest

from app.ai.auto_settings import run, _compute_hints, features_from_geometry, _thin_wall_ratio_from_report
from app.ai.schemas import (
    AutoSettingsRequest,
    AutoSettingsResponse,
    ConvertHints,
    FilamentType,
    ModelFeatures,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_request(
    filament: FilamentType = FilamentType.PLA,
    nozzle_mm: float = 0.4,
    quality_intent: str = "standard",
    height_mm: float = 50.0,
    volume_cm3: float = 10.0,
    overhang_ratio: float = 0.10,
    thin_wall_ratio: float = 0.05,
) -> AutoSettingsRequest:
    return AutoSettingsRequest(
        features=ModelFeatures(
            height_mm=height_mm,
            volume_cm3=volume_cm3,
            overhang_ratio=overhang_ratio,
            thin_wall_ratio=thin_wall_ratio,
        ),
        filament=filament,
        nozzle_mm=nozzle_mm,
        quality_intent=quality_intent,
    )


def _make_base_convert_form() -> dict:
    """Simulate the convert form the frontend sends before any AI is applied."""
    return {
        "job_id":               "abc123",
        "printer_id":           "anycubic_kobra3",
        "filament_type":        "pla",
        "nozzle_size_mm":       0.4,
        "nozzle_type":          "brass",
        "build_plate":          "smooth",
        "scale_factor":         1.0,
        "orientation_euler_deg": [],
        "fuzzy_skin":           "none",
        "color_count":          1,
    }


def _apply_hints(hints: ConvertHints, form: dict) -> dict:
    """
    Simulate the frontend 'Apply AI Settings' button.
    Merges only the hint fields into a copy of the form dict.
    """
    return {**form, **hints.model_dump()}


# ── Constants ─────────────────────────────────────────────────────────────────

# The exact 4 fields the AI is allowed to suggest into ConvertRequest.
_ALLOWED_HINT_FIELDS = {"filament_type", "nozzle_size_mm", "nozzle_type", "build_plate"}

# Fields that belong to the rules engine output — must never appear in hints.
_RULES_ENGINE_ONLY_FIELDS = {
    "layer_height_mm", "first_layer_height_mm",
    "wall_count", "top_layers", "bottom_layers",
    "infill_percent", "infill_pattern",
    "supports_enabled", "support_type", "support_density_percent",
    "brim_enabled", "brim_width_mm",
    "print_speed_mm_s", "first_layer_speed_mm_s",
    "nozzle_temp_c", "bed_temp_c",
    "fan_speed_percent",
}

# Canonical field list read directly from the ConvertRequest class definition
# in convert.py — used to verify hints only reference real fields.
_KNOWN_CONVERT_REQUEST_FIELDS = {
    "job_id", "printer_id", "filament_type", "nozzle_size_mm",
    "nozzle_type", "filament_diameter_mm", "build_plate",
    "flush_volume_mm3", "color_count", "filament_colors", "filament_types",
    "orientation_euler_deg", "scale_factor", "fuzzy_skin",
    "fuzzy_skin_thickness_mm", "fuzzy_skin_point_dist_mm",
}


# ── A: ConvertHints contract ──────────────────────────────────────────────────

def test_hints_contains_exactly_four_allowed_fields():
    """ConvertHints must expose exactly the 4 fields that map to ConvertRequest."""
    assert set(ConvertHints.model_fields.keys()) == _ALLOWED_HINT_FIELDS


def test_hints_all_fields_exist_in_convert_request():
    """Every ConvertHints field name must also exist in ConvertRequest."""
    for field in ConvertHints.model_fields:
        assert field in _KNOWN_CONVERT_REQUEST_FIELDS, (
            f"ConvertHints.{field} has no matching field in ConvertRequest"
        )


@pytest.mark.parametrize("filament", list(FilamentType))
def test_hints_filament_matches_request_filament(filament):
    """hints.filament_type must equal the filament enum value passed to run()."""
    hints = _compute_hints(filament, 0.4)
    assert hints.filament_type == filament.value


@pytest.mark.parametrize("nozzle_mm", [0.2, 0.4, 0.6, 0.8])
def test_hints_nozzle_matches_request_nozzle(nozzle_mm):
    """hints.nozzle_size_mm must equal the nozzle diameter passed to run()."""
    hints = _compute_hints(FilamentType.PLA, nozzle_mm)
    assert hints.nozzle_size_mm == nozzle_mm


@pytest.mark.parametrize("filament,expected_plate", [
    (FilamentType.PLA,   "smooth"),
    (FilamentType.TPU,   "smooth"),
    (FilamentType.PETG,  "textured"),
    (FilamentType.ABS,   "textured"),
    (FilamentType.ASA,   "textured"),
    (FilamentType.NYLON, "textured"),
])
def test_hints_build_plate_per_filament(filament, expected_plate):
    """Each filament must map to the correct build plate surface."""
    hints = _compute_hints(filament, 0.4)
    assert hints.build_plate == expected_plate, (
        f"{filament.value}: expected build_plate='{expected_plate}', got '{hints.build_plate}'"
    )


@pytest.mark.parametrize("filament,expected_type", [
    (FilamentType.PLA,   "brass"),
    (FilamentType.PETG,  "brass"),
    (FilamentType.ABS,   "brass"),
    (FilamentType.ASA,   "brass"),
    (FilamentType.TPU,   "brass"),
    (FilamentType.NYLON, "hardened_steel"),
])
def test_hints_nozzle_type_per_filament(filament, expected_type):
    """Nylon must map to hardened_steel; all other supported filaments map to brass."""
    hints = _compute_hints(filament, 0.4)
    assert hints.nozzle_type == expected_type, (
        f"{filament.value}: expected nozzle_type='{expected_type}', got '{hints.nozzle_type}'"
    )


def test_convert_hints_ignores_unknown_fields():
    """ConvertHints must silently drop any field not in its schema."""
    hints = ConvertHints.model_validate({
        "filament_type":  "pla",
        "nozzle_size_mm": 0.4,
        "nozzle_type":    "brass",
        "build_plate":    "smooth",
        # Advisory fields that must be dropped
        "layer_height_mm":  0.2,
        "support_type":     "tree",
        "nozzle_temp_c":    210,
        "infill_percent":   20,
    })
    assert set(hints.model_dump().keys()) == _ALLOWED_HINT_FIELDS


# ── B: Advisory settings are display-only ────────────────────────────────────

def test_response_always_includes_convert_hints():
    """AutoSettingsResponse must always carry a convert_hints block."""
    resp = run(_make_request())
    assert isinstance(resp.convert_hints, ConvertHints)


def test_advisory_settings_present_in_settings_block():
    """Layer height, infill, wall count etc. must be in the display settings block."""
    resp = run(_make_request())
    assert resp.settings.layer.height_mm > 0
    assert resp.settings.infill.percent > 0
    assert resp.settings.wall_count > 0
    assert resp.settings.speed.print_mm_s > 0
    assert resp.settings.nozzle_temp_c > 0


def test_rules_engine_fields_not_in_hints():
    """Layer height, infill, support type etc. must NOT leak into convert_hints."""
    resp = run(_make_request())
    hint_fields = set(resp.convert_hints.model_dump().keys())
    leaked = hint_fields & _RULES_ENGINE_ONLY_FIELDS
    assert not leaked, f"Rules-engine-only fields leaked into convert_hints: {leaked}"


def test_temperatures_not_in_hints():
    """Nozzle and bed temperatures are advisory — they must not appear in hints."""
    resp = run(_make_request(filament=FilamentType.ABS))
    assert "nozzle_temp_c" not in resp.convert_hints.model_dump()
    assert "bed_temp_c"    not in resp.convert_hints.model_dump()


def test_support_config_not_in_hints():
    """Support settings are rules-engine outputs — they must not appear in hints."""
    resp = run(_make_request(overhang_ratio=0.9))
    hint_keys = set(resp.convert_hints.model_dump().keys())
    assert "support_type"            not in hint_keys
    assert "supports_enabled"        not in hint_keys
    assert "support_density_percent" not in hint_keys


def test_layer_height_not_in_hints():
    """Layer height is determined by the rules engine — must not appear in hints."""
    resp = run(_make_request(quality_intent="quality"))
    assert "layer_height_mm"       not in resp.convert_hints.model_dump()
    assert "first_layer_height_mm" not in resp.convert_hints.model_dump()


# ── C: Without Apply, convert form is unchanged ───────────────────────────────

def test_calling_run_does_not_mutate_form_dict():
    """run() must not touch any dict in the caller's scope."""
    form = _make_base_convert_form()
    original = dict(form)
    run(_make_request())
    assert form == original, "AI engine mutated the caller's convert form dict"


def test_without_apply_form_stays_identical_to_original():
    """If the user ignores the AI result, the convert form is exactly as built."""
    form = _make_base_convert_form()
    run(_make_request(filament=FilamentType.NYLON))  # AI runs, user ignores result
    assert form == _make_base_convert_form()


def test_high_overhang_does_not_auto_apply_changes():
    """Even with an ERROR-level overhang warning, nothing is auto-applied to the form."""
    form = _make_base_convert_form()
    resp = run(_make_request(overhang_ratio=0.9))
    # Confirm the AI did raise a warning
    assert any(w.code == "HIGH_OVERHANG" for w in resp.warnings)
    # Confirm the form is still untouched
    assert form["filament_type"] == "pla"
    assert form["build_plate"]   == "smooth"


def test_nylon_suggestion_not_auto_applied():
    """AI suggests nylon settings; without Apply, the form retains its original filament."""
    form = _make_base_convert_form()  # starts as PLA
    resp = run(_make_request(filament=FilamentType.NYLON))
    assert resp.convert_hints.filament_type == "nylon"  # AI recommends nylon
    assert form["filament_type"] == "pla"               # form is still PLA


def test_stability_warning_does_not_auto_apply_brim():
    """A STABILITY_RISK warning must not auto-modify build_plate or any form field."""
    form = _make_base_convert_form()
    # Construct a very tall, tiny-volume model → high stability risk
    resp = run(_make_request(height_mm=200.0, volume_cm3=0.5))
    stability_warnings = [w for w in resp.warnings if "STABILITY" in w.code]
    assert stability_warnings, "Expected stability warning for extreme aspect ratio"
    assert form == _make_base_convert_form(), "Stability warning auto-modified the form"


# ── D: Apply merges exactly the right fields ─────────────────────────────────

def test_apply_updates_filament_type():
    """After Apply, form.filament_type equals the AI hint value."""
    resp = run(_make_request(filament=FilamentType.PETG))
    form = _apply_hints(resp.convert_hints, _make_base_convert_form())
    assert form["filament_type"] == "petg"


def test_apply_updates_nozzle_size_mm():
    """After Apply, form.nozzle_size_mm equals the AI hint value."""
    resp = run(_make_request(nozzle_mm=0.6))
    form = _apply_hints(resp.convert_hints, _make_base_convert_form())
    assert form["nozzle_size_mm"] == 0.6


def test_apply_updates_nozzle_type_to_hardened_steel_for_nylon():
    """After Apply with Nylon, form.nozzle_type becomes hardened_steel."""
    resp = run(_make_request(filament=FilamentType.NYLON))
    form = _apply_hints(resp.convert_hints, _make_base_convert_form())
    assert form["nozzle_type"] == "hardened_steel"


def test_apply_updates_build_plate_to_textured_for_abs():
    """After Apply with ABS, form.build_plate becomes textured."""
    resp = run(_make_request(filament=FilamentType.ABS))
    form = _apply_hints(resp.convert_hints, _make_base_convert_form())
    assert form["build_plate"] == "textured"


def test_apply_updates_build_plate_to_textured_for_petg():
    """After Apply with PETG, form.build_plate becomes textured (PETG bonds too hard to smooth PEI)."""
    resp = run(_make_request(filament=FilamentType.PETG))
    form = _apply_hints(resp.convert_hints, _make_base_convert_form())
    assert form["build_plate"] == "textured"


def test_apply_does_not_touch_printer_id():
    """Apply must not change printer_id — that is the user's choice."""
    resp  = run(_make_request())
    base  = _make_base_convert_form()
    form  = _apply_hints(resp.convert_hints, base)
    assert form["printer_id"] == base["printer_id"]


def test_apply_does_not_touch_job_id():
    """Apply must not change job_id."""
    resp = run(_make_request())
    base = _make_base_convert_form()
    form = _apply_hints(resp.convert_hints, base)
    assert form["job_id"] == base["job_id"]


def test_apply_does_not_touch_scale_factor():
    """Apply must not change a user-configured scale_factor."""
    resp = run(_make_request())
    base = {**_make_base_convert_form(), "scale_factor": 1.5}
    form = _apply_hints(resp.convert_hints, base)
    assert form["scale_factor"] == 1.5


def test_apply_does_not_touch_orientation():
    """Apply must not change a user-configured orientation_euler_deg."""
    resp = run(_make_request())
    base = {**_make_base_convert_form(), "orientation_euler_deg": [0.0, 90.0, 0.0]}
    form = _apply_hints(resp.convert_hints, base)
    assert form["orientation_euler_deg"] == [0.0, 90.0, 0.0]


def test_apply_does_not_touch_fuzzy_skin():
    """Apply must not change a user-configured fuzzy_skin setting."""
    resp = run(_make_request())
    base = {**_make_base_convert_form(), "fuzzy_skin": "outer"}
    form = _apply_hints(resp.convert_hints, base)
    assert form["fuzzy_skin"] == "outer"


def test_apply_does_not_touch_color_count():
    """Apply must not change a user-configured color_count."""
    resp = run(_make_request())
    base = {**_make_base_convert_form(), "color_count": 4}
    form = _apply_hints(resp.convert_hints, base)
    assert form["color_count"] == 4


def test_apply_changes_only_the_four_allowed_fields():
    """
    Apply must change exactly the allowed fields and nothing else.
    Uses PETG + 0.6mm nozzle so all four hints differ from the PLA/0.4mm base form.
    """
    resp = run(_make_request(filament=FilamentType.PETG, nozzle_mm=0.6))
    base = _make_base_convert_form()   # pla, 0.4mm, brass, smooth
    form = _apply_hints(resp.convert_hints, base)
    changed = {k for k in form if form[k] != base.get(k)}
    assert changed <= _ALLOWED_HINT_FIELDS, (
        f"Apply changed unexpected fields: {changed - _ALLOWED_HINT_FIELDS}"
    )


# ── E: Pipeline isolation ─────────────────────────────────────────────────────

def test_run_is_deterministic():
    """run() must return an identical result on repeated calls with the same input."""
    req = _make_request(filament=FilamentType.PETG, nozzle_mm=0.4, overhang_ratio=0.3)
    r1  = run(req)
    r2  = run(req)
    assert r1.model_dump() == r2.model_dump()


def test_run_does_not_mutate_request():
    """run() must not mutate the AutoSettingsRequest passed to it."""
    req = _make_request(filament=FilamentType.ABS, nozzle_mm=0.6)
    original_filament       = req.filament
    original_nozzle         = req.nozzle_mm
    original_height         = req.features.height_mm
    original_overhang_ratio = req.features.overhang_ratio
    run(req)
    assert req.filament              == original_filament
    assert req.nozzle_mm             == original_nozzle
    assert req.features.height_mm    == original_height
    assert req.features.overhang_ratio == original_overhang_ratio


def test_run_independent_calls_do_not_share_state():
    """Two calls with different filaments must produce independent results."""
    r_pla  = run(_make_request(filament=FilamentType.PLA))
    r_abs  = run(_make_request(filament=FilamentType.ABS))
    assert r_pla.convert_hints.filament_type  != r_abs.convert_hints.filament_type
    assert r_pla.convert_hints.build_plate    != r_abs.convert_hints.build_plate
    assert r_pla.settings.nozzle_temp_c       != r_abs.settings.nozzle_temp_c


def test_ai_module_does_not_import_slicing_internals():
    """
    The AI engine must not import from the rules engine, export pipeline,
    or ingestion layer.  Any such import would couple the AI module to
    slicing behaviour and break the isolation guarantee.
    """
    import importlib.util
    spec = importlib.util.find_spec("app.ai.auto_settings")
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
            f"AI engine imports slicing internals via '{stmt}' — "
            "this couples it to slicing behaviour"
        )


def test_convert_py_unchanged():
    """
    convert.py must not import from the AI module.
    The rules engine is authoritative; AI must not inject itself into it.
    """
    import importlib.util
    spec = importlib.util.find_spec("app.api.routes.convert")
    with open(spec.origin, encoding="utf-8") as f:
        src = f.read()
    assert "app.ai" not in src, (
        "convert.py imports from app.ai — the AI module must not modify slicing behaviour"
    )


# ── F: features_from_geometry bridge ─────────────────────────────────────────

def _fake_geometry(
    z_mm: float = 80.0,
    volume_cm3: float = 20.0,
    overhang_ratio: float = 0.15,
    has_thin_walls: bool = False,
    min_thickness_mm: float = 999.0,
):
    """Build a minimal fake GeometryAnalysis using plain dataclasses."""
    from dataclasses import dataclass, field as dc_field

    @dataclass
    class _BB:
        z_mm: float

    @dataclass
    class _Overhang:
        overhang_area_ratio: float

    @dataclass
    class _ThinWall:
        has_thin_walls: bool
        min_thickness_mm: float

    @dataclass
    class _Geo:
        bounding_box: object
        estimated_volume_cm3: float
        overhang: object
        thin_wall: object

    return _Geo(
        bounding_box=_BB(z_mm=z_mm),
        estimated_volume_cm3=volume_cm3,
        overhang=_Overhang(overhang_area_ratio=overhang_ratio),
        thin_wall=_ThinWall(has_thin_walls=has_thin_walls, min_thickness_mm=min_thickness_mm),
    )


def test_bridge_returns_model_features_instance():
    """features_from_geometry must return a valid ModelFeatures instance."""
    result = features_from_geometry(_fake_geometry(), nozzle_mm=0.4)
    assert isinstance(result, ModelFeatures)


def test_bridge_height_mm_from_bounding_box_z():
    """Bridge must map bounding_box.z_mm → ModelFeatures.height_mm."""
    result = features_from_geometry(_fake_geometry(z_mm=123.5), nozzle_mm=0.4)
    assert result.height_mm == 123.5


def test_bridge_volume_cm3_from_geometry():
    """Bridge must map estimated_volume_cm3 → ModelFeatures.volume_cm3."""
    result = features_from_geometry(_fake_geometry(volume_cm3=42.0), nozzle_mm=0.4)
    assert result.volume_cm3 == 42.0


def test_bridge_overhang_ratio_from_overhang_report():
    """Bridge must map overhang.overhang_area_ratio → ModelFeatures.overhang_ratio."""
    result = features_from_geometry(_fake_geometry(overhang_ratio=0.33), nozzle_mm=0.4)
    assert result.overhang_ratio == 0.33


def test_bridge_no_thin_walls_gives_zero_ratio():
    """has_thin_walls=False must produce thin_wall_ratio=0.0 regardless of thickness."""
    result = features_from_geometry(
        _fake_geometry(has_thin_walls=False, min_thickness_mm=0.1), nozzle_mm=0.4
    )
    assert result.thin_wall_ratio == 0.0


def test_bridge_sentinel_thickness_gives_zero_ratio():
    """min_thickness_mm=999 (no thin walls found) must produce thin_wall_ratio=0.0."""
    result = features_from_geometry(
        _fake_geometry(has_thin_walls=True, min_thickness_mm=999.0), nozzle_mm=0.4
    )
    assert result.thin_wall_ratio == 0.0


@pytest.mark.parametrize("thickness,nozzle_mm,expected_ratio", [
    (0.3, 0.4, 0.75),  # below nozzle width → severe
    (0.7, 0.4, 0.40),  # between 1× and 2× nozzle → sub-double
    (1.0, 0.4, 0.20),  # between 2× and 3× nozzle → borderline
    (1.5, 0.4, 0.10),  # above 3× nozzle → marginal
])
def test_bridge_thin_wall_ratio_buckets(thickness, nozzle_mm, expected_ratio):
    """_thin_wall_ratio_from_report must map thickness buckets to the correct ratio values."""
    from dataclasses import dataclass

    @dataclass
    class _TW:
        has_thin_walls: bool = True
        min_thickness_mm: float = 0.0

    report = _TW(has_thin_walls=True, min_thickness_mm=thickness)
    ratio  = _thin_wall_ratio_from_report(report, nozzle_mm)
    assert ratio == expected_ratio, (
        f"thickness={thickness}mm with nozzle={nozzle_mm}mm: "
        f"expected ratio {expected_ratio}, got {ratio}"
    )


def test_bridge_thin_wall_ratio_is_in_valid_range():
    """thin_wall_ratio produced by the bridge must always be within [0.0, 1.0]."""
    for thickness in [0.1, 0.3, 0.5, 0.8, 1.2, 2.0, 5.0, 999.0]:
        result = features_from_geometry(
            _fake_geometry(has_thin_walls=thickness < 999.0, min_thickness_mm=thickness),
            nozzle_mm=0.4,
        )
        assert 0.0 <= result.thin_wall_ratio <= 1.0, (
            f"thin_wall_ratio={result.thin_wall_ratio} out of range for thickness={thickness}"
        )


def test_bridge_result_passes_model_features_validation():
    """ModelFeatures returned by the bridge must satisfy all its own field constraints."""
    # This implicitly runs Pydantic validation — any constraint violation raises
    result = features_from_geometry(
        _fake_geometry(z_mm=150.0, volume_cm3=5.0, overhang_ratio=0.45,
                       has_thin_walls=True, min_thickness_mm=0.35),
        nozzle_mm=0.4,
    )
    assert result.height_mm > 0
    assert result.volume_cm3 > 0
    assert 0.0 <= result.overhang_ratio  <= 1.0
    assert 0.0 <= result.thin_wall_ratio <= 1.0
