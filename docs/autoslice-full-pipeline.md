# AutoSlice Full Universal3MF Pipeline

Step 16 unifies detection, parsing, intelligence, target translation, export and validation into the production conversion path.

## Production flow

`ConversionService` remains the secure outer boundary:

1. Read and validate the OPC/ZIP container.
2. Detect the source slicer with confidence gating.
3. Parse once into immutable `Universal3MF`.
4. Execute `FullUniversal3MFPipeline`.
5. Export through the registered target exporter.
6. Run target validation and reparse the generated package.
7. Create a collision-safe filename and owner-scoped download reference.

The inner pipeline produces one `PipelineSnapshot` containing target profile, project analysis, geometry/printability, support plan, placement plan, OptimizationPlan, optimized document, TranslationPlan, weighted translation report and ordered stage timings.

## Analyze and convert consistency

`POST /api/universal-analyze` uses the same pipeline in `analyze_only` mode. It returns a serializable snapshot view without applying or exporting. Conversion recomputes deterministically from the same document and context, applies the exact plan once, performs required geometry/placement re-analysis, then creates the TranslationPlan from the optimized document.

`PRESERVE` still runs compatibility and intelligence analysis when a target profile exists, but produces no applied setting, geometry, support, or placement changes. Optimization and translation remain distinct models and stages.

## Failure and safety boundaries

Detection, parser, translation/intelligence, export and validation errors retain stable `ConversionErrorCode` categories. Hard limits block application before export. Output is not downloadable until target validation and successful target reparse complete. Downloads remain user-scoped and are revalidated on access.

Stage durations are observational and excluded from semantic equality. The deterministic snapshot content—plans, decisions, ordering, explanations and scores—does not depend on timing or randomness.

## Current target scope

The parser registry accepts supported Bambu, Orca, Prusa, Cura, Anycubic and core 3MF inputs according to detection confidence and fixture coverage. The production exporter registry remains deliberately conservative: Anycubic is the validated writable target. Additional targets require their own exporter and validator before registration.
