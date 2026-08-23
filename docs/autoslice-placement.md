# AutoSlice Build Plate Placement

Step 14 introduces deterministic build-item placement after orientation and support planning. The engine works with Universal3MF affine transforms and changes only their translation components, preserving object geometry and any selected rotation.

## Analysis and candidates

`PlacementAnalyzer` resolves current object bounding boxes, positions, build/plate bounds, collisions and profile-declared spacing. It reports `OUTSIDE_BUILD_PLATE`, `OBJECT_COLLISION`, `INSUFFICIENT_SPACING`, `UNNECESSARY_EMPTY_SPACE`, and multi-plate preservation diagnostics.

The bounded candidate set contains the current placement plus row, grid, and shelf packing. Stable object order, candidate order, and tie-breaking make output deterministic. Each candidate exposes fit, collision count, spacing violations (or `null` when the printer profile has no spacing fact), plate-envelope utilization, and separate scoring components for fit, collisions, spacing, utilization, support implications, and orientation implications.

## Modes and safety

`PRESERVE` analyzes but never applies positions. `AUTOSLICE` may select a fitting, collision-free, spacing-valid candidate when the current placement is invalid or the score improves materially. Each `PlacementChange` records build-item index, object, old/new transform and position, reason, rule, confidence, and application state.

Application preserves the current 3×3 rotation matrix and only replaces XYZ translation. Mandatory post-application analysis rejects build-volume, collision, or explicit-spacing violations.

## Plates and limitations

`PlateAssignment` represents multiple plates, but automatic cross-plate distribution is deliberately disabled. Existing multi-plate projects are preserved. The current engine packs direct build items by transformed AABB; component expansion, polygon nesting, concave footprints, sequential-print head clearance, support-footprint collision, and true 2D bin packing remain future work. Unknown minimum spacing remains `UNKNOWN` rather than receiving an invented hardcoded value.
