# AutoSlice Geometry Intelligence

Step 12 adds a deterministic, Three.js-independent geometry and printability pass over `Universal3MF` meshes.

## Analysis and validation

`GeometryAnalyzer` validates finite and reasonably bounded coordinates, vertex references, triangle limits, zero-area and duplicate triangles, open boundaries, and non-manifold edges. Invalid indices, hostile coordinates, and resource-limit violations block analysis; repairable topology findings are warnings.

Per-object output contains bounds and dimensions, triangle count, center of mass, bounding principal axes, surface-derived build contact, overhang faces, thin/small-feature classification, wall feasibility, build-volume fit, placement diagnostics, and an orientation recommendation. Self-intersection remains an indicator-level future extension.

## Orientation

The bounded candidate set is identity, X ±90°, Y ±90°, and X 180°. Each candidate reports separate build-fit, contact, overhang, height, and stability components. Stable score ordering makes ties deterministic. Confidence comes from the improvement and gap to the runner-up.

Modes are `AUTO`, `PRESERVE`, and architecturally prepared `MANUAL`. A geometry transform is separately traceable in `OptimizationPlan.geometry_changes`; it is never represented as a print setting. Preserve mode never applies it. Auto mode requires configured improvement and high confidence. Multi-object builds receive analysis but no independent automatic rotations. Applied transforms trigger mandatory geometry re-analysis and are rejected on a blocked result or collision.

## Overhangs and supports

Face normals are compared with the configurable build-direction threshold. Machine-readable moderate and critical face indices, areas, percentages, build-contact faces, collision boxes, and the build-volume box support later frontend overlays. Support output is explicitly a recommendation; no support mesh is generated. Existing support blockers/enforcers remain preserved by Universal3MF and future regional support planning must reconcile them.

## Printability and safety

Project status aggregates object health, target fit, thin/small features, placement, overhangs, AABB collision, material/nozzle rules, and unknown object spacing. Status values are `GOOD`, `WARNING`, `BLOCKED`, and `UNKNOWN`. Analysis timings separate validation, geometry, overhang, orientation, collision, and total work.

Current limitations include axis-aligned collision only, bounding-axis rather than covariance-based principal axes, heuristic bridge/thin-feature indicators, no reliable object-spacing profile field, no mesh-level self-intersection test, and no automatic multi-object orientation or placement.
