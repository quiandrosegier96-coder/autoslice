# Ultimaker Cura fixtures

No real Cura-generated project fixture is available. Cura tests requiring real files skip explicitly. Synthetic packages test only architectural behavior and cannot certify Cura compatibility.

Requested files:

- `cura_basic.3mf` — single object, Cura version, printer and common settings
- `cura_multi_object.3mf` — independent objects/components/transforms
- `cura_multimaterial.3mf` — explicit materials and extruder assignments
- `cura_multi_part.3mf` — grouped multipart model
- `cura_modifier.3mf` — infill/cutting/modifier meshes
- `cura_supports.3mf` — support blockers/enforcers and support settings
- `cura_multi_build.3mf` — plate/build behavior if supported

Document Cura version, printer, extruders, materials, object/build expectations and redistribution permission for every fixture.
