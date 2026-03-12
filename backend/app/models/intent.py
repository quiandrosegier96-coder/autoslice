"""
AutoSlice — ModelIntent data model.
Slicer-agnostic summary of what the model needs, produced by the Normalization layer.
"""

from dataclasses import dataclass
from typing import Literal

from app.models.geometry import GeometryAnalysis


@dataclass
class ModelIntent:
    difficulty: Literal["easy", "moderate", "hard"]
    needs_supports: bool
    support_density_hint: Literal["light", "normal", "heavy"]
    needs_brim: bool
    size_class: Literal["small", "medium", "large"]
    has_fine_detail: bool
    is_structurally_risky: bool
    raw_geometry: GeometryAnalysis
