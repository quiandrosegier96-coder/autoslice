"""
AutoSlice — Bambu/MakerWorld metadata parser.
Reads Bambu-specific config files from the extracted archive.
NOTE: We do NOT use these settings in our output.
We read them only for informational context (e.g. original filament type, model name).
"""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class BambuMetadata:
    model_name: str = ""
    original_filament: str = ""      # informational only
    original_printer: str = ""       # informational only
    plate_count: int = 1
    raw_configs: dict = field(default_factory=dict)


def parse_bambu_metadata(metadata_files: list[Path]) -> BambuMetadata:
    """
    Extract informational metadata from Bambu config files.
    These are read for context only — no settings are carried over to output.
    """
    raise NotImplementedError("Bambu metadata parsing not yet implemented — Phase 3.")
