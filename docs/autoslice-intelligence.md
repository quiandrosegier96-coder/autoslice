# AutoSlice Intelligence Engine

Step 11 introduces a deterministic layer between `Universal3MF` parsing and target translation. It performs no network, LLM, random, or machine-learning calls.

## Flow

`Universal3MF -> ProjectAnalyzer -> TargetProfile -> OptimizationPlan -> optimized Universal3MF -> TranslationPlan -> export -> validation`

`OptimizationPlan` and `TranslationPlan` are deliberately separate. The former records intentional target-aware setting changes; the latter maps source capabilities and values to target semantics.

## Profiles

Profiles are slicer-neutral immutable models:

- `PrinterProfile`: identity, build volume, nozzle/material support, limits and capabilities.
- `NozzleProfile`: diameter, material, layer-height bounds, recommended height and line-width range.
- `FilamentProfile`: hotend/bed ranges, flow, cooling, density, speed and nozzle compatibility.
- `TargetProfile`: binds a target slicer to a printer, nozzle and selected filament without adding vendor-specific fields to the common model.

The initial conservative filament catalogue contains PLA, PETG and TPU. Printer facts reuse the existing JSON printer catalogue.

## Analysis

`ProjectAnalyzer` is read-only. It reports object count, object and project bounds/dimensions, triangle-derived volume and surface area, material mappings, known process settings, build-volume usage and simple small-feature indicators. It never scales or rotates geometry. Orientation and support recommendations are modeled but are not automatically applied in Step 11.

## Rules and priorities

Implemented rules are `BUILD_VOLUME_LIMIT`, `NOZZLE_LAYER_HEIGHT_RANGE`, `NOZZLE_FIRST_LAYER_HEIGHT_RANGE`, `MATERIAL_TEMPERATURE_RANGE`, `MATERIAL_BED_TEMPERATURE_RANGE`, `FILAMENT_COMPATIBILITY`, source/target material mismatch, and `TOOL_CAPABILITY`.

Priority is deterministic:

`SAFETY > HARD_LIMIT > COMPATIBILITY > QUALITY > PERFORMANCE > PREFERENCE`

For conflicting changes to one setting, the highest priority wins. Equal priorities use the stable rule identifier. Automatic writes are additionally restricted by an explicit setting allowlist. Everything else is preserved.

## Modes and diagnostics

- `PRESERVE` creates no automatic setting changes. Applicable rules remain recommendations.
- `AUTOSLICE` applies allowlisted changes and preserves a trace containing old value, new value, reason, rule, confidence, priority and category.
- `CUSTOM` and quality/speed/material profiles have model placeholders but no Step 11 behavior.

An outside build volume, unsupported target filament, or excess required tools blocks application/export. Material mismatch is a warning and never silently substitutes filament. Units remain millimetres and no implicit scaling occurs.

## Compatibility

The optimization report separates source compatibility, target compatibility, optimization impact, and final compatibility, plus supported/approximated/preserved/unsupported percentages. Translation retains its existing severity-weighted scoring. Scores are derived from rule outcomes, not raw warning counts.

## API and performance

`POST /api/universal-analyze` accepts an uploaded job and target selection and returns source data, project analysis, target profile and the dry-run optimization plan. It writes no output. `POST /api/universal-convert` recomputes the same deterministic plan and then translates, exports and validates.

Analysis and rule evaluation are synchronous CPU-local operations. Existing conversion timings continue to measure parse, translation (including intelligence), export, validation and total time.

## Future AI integration

Future AI may propose orientation, supports or profile preferences, but proposed changes must still become explicit rules/decisions and pass the same allowlist, priority resolution, hard limits, traceability and deterministic export safeguards.
