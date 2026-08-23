"""Central collision-safe AutoSlice output naming."""

from pathlib import Path


def autoslice_output_filename(original_filename: str, existing: set[str] | None = None) -> str:
    source = Path(original_filename).name
    stem = Path(source).stem or "project"
    existing_names = {name.casefold() for name in (existing or set())}
    base = stem
    candidate = f"{base}_AutoSlice.3mf" if not stem.casefold().endswith("_autoslice") else f"{base}_2.3mf"
    counter = 2 if not stem.casefold().endswith("_autoslice") else 3
    while candidate.casefold() in existing_names:
        root = f"{stem}_AutoSlice" if not stem.casefold().endswith("_autoslice") else stem
        candidate = f"{root}_{counter}.3mf"
        counter += 1
    return candidate
