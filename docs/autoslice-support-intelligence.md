# AutoSlice Support Intelligence

Step 13 adds deterministic support analysis and planning after geometry intelligence. It does not embed or fabricate support meshes.

## Regions and clustering

`SupportAnalyzer` consumes the validated object meshes and critical/moderate face indices from `PrintabilityReport`. Faces sharing an edge are clustered into stable `SupportRegion` records. Each region reports its object and face IDs, area, area-weighted angle and centroid, severity, estimated build-plate accessibility, requirement and confidence.

Disconnected islands remain separate regions. Estimated support volume is explicitly heuristic (`area × vertical distance × sparse-volume factor`), not an exact sliced volume.

## Strategies and target capabilities

Plans can select `NONE`, `BUILD_PLATE_ONLY`, `NORMAL`, `TREE`, `ORGANIC`, or `AUTO`, but selection is restricted to the target profile's declared support types. The verified Anycubic target currently exposes normal and tree planning. Capability reporting includes support generation, types, blockers and enforcers.

The existing geometric tree-support engine is intentionally not invoked by this layer. It remains an implementation that can later sit behind a generation adapter after its output can be embedded and target-validated reliably.

## Source semantics and modes

Existing `SupportConfig`, opaque payloads, blockers, enforcers and support-role objects remain preserved. An enforcer can elevate a region to required. A blocker overlapping an analyzed requirement produces `SUPPORT_CONFLICT` and prevents automatic application.

`PRESERVE` returns the analysis while making no change. `AUTOSLICE` may enable supports and choose a target-supported strategy only when required regions have high confidence and no blocker conflict exists. Every proposed/applied support change is separate from settings and geometry transforms and records old value, new value, reason, rule, confidence and applied state.

Diagnostics are `SUPPORT_REQUIRED`, `SUPPORT_RECOMMENDED`, `SUPPORT_NOT_REQUIRED`, `SUPPORT_UNSUPPORTED`, and `SUPPORT_CONFLICT`. `/api/universal-analyze` returns the complete machine-readable `support_plan` alongside printability and optimization data.

## Limitations

Build-plate accessibility is currently a conservative centroid-height estimate rather than ray-cast path planning. Region intersection with opaque painted blocker payloads cannot be computed until those payload formats are semantically decoded. Support volume is estimated. No interface layers, support paths, collision-free branches, support mesh, or G-code are generated in Step 13.
