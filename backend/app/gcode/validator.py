"""
AutoSlice — G-code validator and auto-corrector.

Detects common G-code issues that cause extrusion failures on FDM printers,
with a focus on relative-extrusion (M83) safety.

Rules implemented
─────────────────
1. M83 (relative extrusion):
   - Requires G92 E0 at start and at every layer change.
   - If resets are absent, auto-injects them and marks the file as "fixed".

2. M82 (absolute extrusion):
   - Warns if excessive G92 E0 resets exist (duplicate post-processing scripts).
   - Warns if very high absolute E values are found (missing reset elsewhere).

3. Missing extrusion mode:
   - Warns when neither M82 nor M83 is present (slicer default assumed).

4. Layer-change consistency:
   - Detects common layer markers: ;LAYER:N, ;LAYER_CHANGE, ; layer:, etc.
   - Used to count expected reset positions and validate coverage.

5. Suspicious extrusion jumps:
   - Flags absolute E values over 100 (almost always a missing reset).

Auto-fix strategy
─────────────────
All fixes are injected at the correct position in the line list.
The original G-code is never truncated — only lines are inserted.
Each injected line carries a trailing comment so it is auditable.

Returns
───────
GcodeValidationResult dataclass — serializable to JSON for the API response.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


# ── Constants ─────────────────────────────────────────────────────────────────

# Common layer-boundary markers emitted by OrcaSlicer / PrusaSlicer / Cura
_LAYER_MARKER_RE = re.compile(
    r"^\s*;"
    r"(?:"
    r"\s*LAYER[:\s_]"       # ;LAYER:N, ;LAYER N, ;LAYER_CHANGE
    r"|layer_change"        # ;layer_change (lowercase)
    r"|LAYER_CHANGE"        # ;LAYER_CHANGE
    r"|Z\s+CHANGE"          # ;Z CHANGE (some slicers)
    r")",
    re.IGNORECASE,
)

# Maximum G-code payload accepted by the validator (10 MB)
MAX_GCODE_BYTES = 10 * 1024 * 1024


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class GcodeValidationResult:
    status: Literal["ok", "warning", "fixed", "error"]

    has_m83: bool
    has_m82: bool
    g92_e0_count: int
    layer_count: int
    line_count: int

    issues: list[str] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)

    # Only populated when status == "fixed"
    fixed_gcode: str | None = None


# ── Public entry point ────────────────────────────────────────────────────────

def validate_gcode(gcode_text: str) -> GcodeValidationResult:
    """
    Validate G-code text, auto-fix safe issues, and return a structured result.

    Parameters
    ----------
    gcode_text : str
        Raw G-code as a single string (newline-separated lines).

    Returns
    -------
    GcodeValidationResult
        status:
            "ok"      — no issues found
            "warning" — issues found but no safe auto-fix available
            "fixed"   — issues found and safely corrected
            "error"   — critical issue; output should be blocked
    """
    lines = gcode_text.splitlines()

    has_m83 = _has_command(lines, "M83")
    has_m82 = _has_command(lines, "M82")

    layer_indices = _find_layer_indices(lines)
    g92_e0_count  = _count_g92_e0(lines)

    issues: list[str] = []
    fixes:  list[str] = []
    fixed_lines: list[str] | None = None
    status: Literal["ok", "warning", "fixed", "error"] = "ok"

    # ── Rule 1: M83 without G92 E0 resets ────────────────────────────────────
    if has_m83:
        if g92_e0_count == 0:
            issues.append(
                "Relative extruder mode (M83) detected — no G92 E0 reset found. "
                "This causes progressive extrusion drift and will lead to under- or "
                "over-extrusion on every layer."
            )
            fixed_lines, n_injected = _inject_g92_e0(lines, layer_indices)
            if n_injected > 0:
                fixes.append(
                    f"Inserted G92 E0 at {n_injected} layer change(s)"
                )
            # Also inject immediately after M83
            fixed_lines, added_after_m83 = _inject_after_command(fixed_lines, "M83")
            if added_after_m83:
                fixes.append("Inserted G92 E0 immediately after M83 (initial reset)")
            status = "fixed"

        elif layer_indices and g92_e0_count < len(layer_indices) * 0.5:
            # Some resets exist but coverage is < 50% of layers
            issues.append(
                f"M83 active: only {g92_e0_count} G92 E0 resets found for "
                f"{len(layer_indices)} layer changes. "
                "Some layers may extrude incorrectly."
            )
            status = "warning"

        else:
            # M83 with adequate resets — informational only
            issues.append(
                f"Relative extruder mode (M83) with {g92_e0_count} G92 E0 resets — "
                f"coverage looks adequate for {len(layer_indices)} detected layer changes."
            )

    # ── Rule 2: M82 edge cases ────────────────────────────────────────────────
    elif has_m82:
        threshold = max(len(layer_indices) * 2, 10)
        if g92_e0_count > threshold:
            issues.append(
                f"Absolute extrusion (M82) with {g92_e0_count} G92 E0 resets — "
                "unusually high reset count may indicate duplicate post-processing scripts."
            )
            if status == "ok":
                status = "warning"

        # Check for very high absolute E values
        max_e = _max_absolute_e(lines)
        if max_e > 100.0:
            issues.append(
                f"Very high absolute E value detected (E{max_e:.2f}). "
                "In absolute extrusion mode this is unusual and may indicate "
                "a missing G92 E0 reset after a filament change."
            )
            if status == "ok":
                status = "warning"

    # ── Rule 3: no extrusion mode declared ───────────────────────────────────
    elif len(lines) > 50:
        issues.append(
            "No extrusion mode command found (M82 or M83). "
            "The printer firmware default will be used — "
            "verify this matches your slicer configuration."
        )
        if status == "ok":
            status = "warning"

    return GcodeValidationResult(
        status=status,
        has_m83=has_m83,
        has_m82=has_m82,
        g92_e0_count=g92_e0_count,
        layer_count=len(layer_indices),
        line_count=len(lines),
        issues=issues,
        fixes_applied=fixes,
        fixed_gcode="\n".join(fixed_lines) if fixed_lines else None,
    )


# ── Private helpers ───────────────────────────────────────────────────────────

def _strip_comment(line: str) -> str:
    """Return the non-comment portion of a G-code line."""
    idx = line.find(";")
    return line[:idx] if idx != -1 else line


def _has_command(lines: list[str], cmd: str) -> bool:
    """True if any line contains the bare command token (not in a comment)."""
    pattern = re.compile(r"\b" + re.escape(cmd) + r"\b", re.IGNORECASE)
    return any(pattern.search(_strip_comment(l)) for l in lines)


def _find_layer_indices(lines: list[str]) -> list[int]:
    """Return line indices of layer-boundary comment markers."""
    return [i for i, l in enumerate(lines) if _LAYER_MARKER_RE.match(l)]


def _count_g92_e0(lines: list[str]) -> int:
    """Count occurrences of G92 E0 (extruder reset command)."""
    pattern = re.compile(r"\bG92\s+E0\b", re.IGNORECASE)
    return sum(1 for l in lines if pattern.search(_strip_comment(l)))


def _max_absolute_e(lines: list[str]) -> float:
    """Return the highest E value seen in movement commands."""
    pattern = re.compile(r"\bE(-?\d+(?:\.\d+)?)\b", re.IGNORECASE)
    max_e = 0.0
    for l in lines:
        code = _strip_comment(l)
        if not (code.upper().startswith("G0") or code.upper().startswith("G1")):
            continue
        for m in pattern.finditer(code):
            val = float(m.group(1))
            if val > max_e:
                max_e = val
    return max_e


def _inject_g92_e0(
    lines: list[str],
    layer_indices: list[int],
) -> tuple[list[str], int]:
    """
    Insert 'G92 E0' before each layer marker.

    Inserts in reverse order so earlier indices stay valid.
    Returns (modified_lines, number_of_injections).
    """
    if not layer_indices:
        return lines, 0

    working = list(lines)
    inject_line = "G92 E0 ; auto-injected — relative extrusion safety reset"

    for idx in reversed(layer_indices):
        working.insert(idx, inject_line)

    return working, len(layer_indices)


def _inject_after_command(
    lines: list[str],
    cmd: str,
) -> tuple[list[str], bool]:
    """
    Insert 'G92 E0' on the line immediately after the first occurrence of `cmd`.

    Returns (modified_lines, was_injected).
    """
    pattern = re.compile(r"\b" + re.escape(cmd) + r"\b", re.IGNORECASE)
    for i, l in enumerate(lines):
        if pattern.search(_strip_comment(l)):
            working = list(lines)
            working.insert(
                i + 1,
                f"G92 E0 ; auto-injected after {cmd} — initial extruder reset",
            )
            return working, True
    return lines, False
