"""
AutoSlice — Benchmark runner.

Replays a set of test .3mf files through the full analysis + rules engine
and captures the decision trace + settings delta for each run.

Usage (CLI):
    python -m app.diagnostics.benchmark \
        --cases data/benchmark_cases.json \
        --out   data/benchmark_results.json

benchmark_cases.json format:
    [
      {
        "label": "tall_vase",
        "archive_path": "data/benchmark_models/tall_vase.3mf",
        "printer_id": "kobra3",
        "filament": "pla",
        "nozzle_mm": 0.4
      }
    ]
"""

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BenchmarkCase:
    label: str
    archive_path: Path
    printer_id: str
    filament: str
    nozzle_mm: float


@dataclass
class BenchmarkResult:
    label: str
    intent: dict
    settings: dict
    delta: dict
    trace: list[dict]
    error: str | None = None


def run_benchmark(cases: list[BenchmarkCase]) -> list[BenchmarkResult]:
    # Lazy imports — keep this module importable without full app context
    from app.diagnostics.models import DecisionTrace
    from app.geometry.analyzer import analyze
    from app.ingestion.unpacker import unpack
    from app.models.printer import FilamentType
    from app.normalization.intent import normalize
    from app.parser.model_parser import parse_model_files
    from app.rules.base_profiles import load_base_profile
    from app.rules.engine import generate_settings
    from app.rules.printer_loader import load_printer_profile

    results = []
    for case in cases:
        try:
            extract_dir = case.archive_path.parent / "bench_extract" / case.label
            archive  = unpack(case.archive_path, extract_dir)
            model    = parse_model_files(archive.model_files, archive.object_type_map)
            geometry = analyze(model)
            intent   = normalize(geometry)
            printer  = load_printer_profile(case.printer_id)
            filament = FilamentType(case.filament)
            base     = load_base_profile(printer)
            trace    = DecisionTrace(case.label, case.printer_id, case.filament, case.nozzle_mm)
            settings = generate_settings(intent, printer, filament, case.nozzle_mm, trace)
            results.append(BenchmarkResult(
                label    = case.label,
                intent   = dataclasses.asdict(intent),
                settings = dataclasses.asdict(settings),
                delta    = _diff_settings(
                               json.dumps(dataclasses.asdict(base)),
                               json.dumps(dataclasses.asdict(settings)),
                           ),
                trace    = trace.to_list(),
            ))
        except Exception as exc:
            results.append(BenchmarkResult(
                label=case.label, intent={}, settings={}, delta={}, trace=[],
                error=str(exc),
            ))
    return results


def compare_runs(a: list[BenchmarkResult], b: list[BenchmarkResult]) -> dict:
    """Diff two benchmark runs by label. Use before/after an engine change."""
    index_a = {r.label: r for r in a}
    index_b = {r.label: r for r in b}
    out = {}
    for label in index_a.keys() & index_b.keys():
        sa = index_a[label].settings
        sb = index_b[label].settings
        diff = {k: {"a": sa.get(k), "b": sb.get(k)}
                for k in sa if sa.get(k) != sb.get(k)}
        if diff:
            out[label] = diff
    return out


def _diff_settings(base_json: str, final_json: str) -> dict:
    base  = json.loads(base_json)
    final = json.loads(final_json)
    return {k: {"from": base.get(k), "to": v}
            for k, v in final.items() if v != base.get(k)}


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="AutoSlice benchmark runner")
    parser.add_argument("--cases", required=True, help="Path to benchmark_cases.json")
    parser.add_argument("--out",   required=True, help="Output JSON path")
    parser.add_argument("--compare", default=None, help="Previous results JSON to diff against")
    args = parser.parse_args()

    cases_data = json.loads(Path(args.cases).read_text())
    cases = [
        BenchmarkCase(
            label        = c["label"],
            archive_path = Path(c["archive_path"]),
            printer_id   = c["printer_id"],
            filament     = c["filament"],
            nozzle_mm    = c["nozzle_mm"],
        )
        for c in cases_data
    ]

    print(f"Running {len(cases)} benchmark case(s)…")
    results = run_benchmark(cases)

    output = [dataclasses.asdict(r) for r in results]
    Path(args.out).write_text(json.dumps(output, indent=2, default=str))
    print(f"Results written to {args.out}")

    errors = [r for r in results if r.error]
    if errors:
        print(f"\n{len(errors)} case(s) failed:")
        for r in errors:
            print(f"  {r.label}: {r.error}")
        sys.exit(1)

    if args.compare:
        prev = [BenchmarkResult(**r) for r in json.loads(Path(args.compare).read_text())]
        diff = compare_runs(prev, results)
        if diff:
            print("\nSettings that changed vs previous run:")
            print(json.dumps(diff, indent=2, default=str))
        else:
            print("\nNo settings changes vs previous run.")
