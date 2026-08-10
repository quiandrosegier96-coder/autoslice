# PrusaSlicer fixtures

No real PrusaSlicer-generated fixture is currently available. Tests requiring these files skip explicitly; synthetic packages only test architecture and must not be used to certify compatibility.

Requested fixture inventory:

- `prusa_basic.3mf` — one object and common print settings
- `prusa_multi_object.3mf` — separate objects, components and transforms
- `prusa_multimaterial.3mf` — MMU/tool, object and triangle assignments
- `prusa_multi_plate.3mf` — plate/build semantics
- `prusa_modifier.3mf` — modifier geometry, target and settings
- `prusa_supports.3mf` — blockers, enforcers, painted/organic supports

For each fixture record PrusaSlicer version, expected objects/plates/tools, printer profile, special features and redistribution permission. Never add customer projects without permission.
