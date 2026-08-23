# AutoSlice Advanced Print Optimization

Step 15 centralizes measurable print-setting trade-offs while keeping optimization separate from target translation.

## Profiles and objectives

`OptimizationProfile` supports `BALANCED`, `QUALITY`, `FAST`, and `MATERIAL_SAVING`. Each profile supplies configurable non-negative weights totaling 1.0 across `quality`, `reliability`, `speed`, and `material`. Callers may provide validated custom weights.

The bounded candidate set contains source preservation plus balanced, quality, fast, and material-saving variants. Candidates may vary layer height, walls, infill, speed, nozzle/bed temperature, cooling, and the current support strategy. Geometry orientation, support, and placement remain separate traced plan sections produced by their specialist analyzers.

## Scoring and safety

Scores use source/target measurements: layer height relative to nozzle range, wall and infill quantities, print speed relative to filament/printer limits, temperature compatibility, and whether supports consume material. There is no randomness, machine learning, or network inference.

Every candidate is checked against project hard blocks, nozzle layer bounds, material hotend/bed ranges, and printer speed. A violating candidate is non-viable regardless of objective score. In the combined decision engine, safety, hard-limit, compatibility, and quality rules outrank objective preferences through the existing deterministic conflict resolver.

`OptimizationExplanation` records setting, old/new values, rule, reason, and measured delta for every objective. `ANALYZE ONLY` returns the same candidate preview and explanations without applying changes. `/api/universal-analyze` exposes `optimization_preview`; conversion accepts an `optimization_profile` and recomputes the deterministic plan.

## Performance and limitations

Candidate evaluation is bounded to five small records and reports `benchmark_ms`. Scores are comparative engineering heuristics, not predicted print time, tensile strength, surface roughness, or exact filament mass. Future calibration profiles can replace individual metrics without changing hard-limit enforcement, explanations, or translation separation.
