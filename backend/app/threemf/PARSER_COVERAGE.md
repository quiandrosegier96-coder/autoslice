# Universal3MF parser coverage — Step 3

No real Bambu Studio or Anycubic Slicer fixture is currently available. The table below describes implemented behavior, not certified slicer compatibility.

| Source data | Bambu adapter | Anycubic adapter | Notes |
|---|---|---|---|
| Core model objects and meshes | Parsed semantically | Parsed semantically | Object IDs are not flattened. |
| Core components and transforms | Parsed semantically | Parsed semantically | Cross-model Production Extension paths still require real-fixture work. |
| Core build items | Parsed semantically | Parsed semantically | Plate IDs require slicer metadata evidence. |
| Core base materials | Parsed semantically | Parsed semantically | Material identity remains separate from tools. |
| Triangle property references | Parsed semantically | Parsed semantically | No round-robin mapping is introduced. |
| Textures and texture groups | Parsed semantically | Parsed semantically | Binary texture payload is retained. |
| `project_settings.config` known keys | Parsed semantically | Parsed semantically | Shared PrusaSlicer-family mapping. |
| Unknown project settings | Preserved opaque and in `source_values` | Preserved opaque and in `source_values` | Not silently discarded. |
| Filament arrays/tool slots | Parsed semantically | Parsed semantically | Explicit slot identity only. |
| `model_settings.config` explicit extruder mapping | Parsed semantically | Parsed semantically | Applied only when an explicit mapping exists. |
| Object/part subtype roles | Parsed semantically when recognized | Parsed semantically when recognized | Unknown roles remain unknown/opaque. |
| Plate metadata | Preserved opaque | Preserved opaque | Unsupported semantically until real fixtures exist. |
| Painted colors/seams/supports | Preserved opaque | Preserved opaque | Unsupported semantically until real fixtures exist. |
| Slicer thumbnails and unknown package parts | Preserved opaque | Preserved opaque | Export policy decides whether target copying is safe. |
| Legacy Anycubic mesh flattening | Not part of parser | Adapter limitation | Reported as `SUPPORTED_WITH_LIMITS`, high impact. |
| Legacy round-robin multicolor | Never used | Adapter limitation | Reported as `APPROXIMATED`, high impact. |

Real-fixture certification must replace assumptions in this table before public support claims are made.

## OrcaSlicer

No real OrcaSlicer fixture is present. `OrcaParser` is therefore experimental and gated by explicit Orca detection evidence. It parses core 3MF plus the same centralized, known project-setting subset used for the PrusaSlicer-derived family. Orca-specific plates, painting, modifier targeting and support payloads remain opaque. See `capabilities/profiles.py`; every Orca capability note states its fixture status.

## PrusaSlicer

No real PrusaSlicer fixture is present. `PrusaParser` requires multiple independent signals and combines `CoreThreeMFParser` with semantic Prusa/Bambu/Orca-family setting aliases. Unknown package parts and setting keys are retained as opaque/source values. Multi-plate, MMU painting, modifier targeting and support semantics remain fixture-unverified.

| Feature | Bambu | Orca | Prusa | Anycubic target |
|---|---|---|---|---|
| Core objects/transforms | Implemented, fixture-unverified | Implemented, fixture-unverified | Implemented, fixture-unverified | Implemented, fixture-unverified |
| Layer height/walls/infill | Mapped subset | Mapped subset | Mapped subset | Exported from Universal settings |
| Materials/tools | Limited | Limited | Limited | Explicit mappings only |
| Supports/painting | Opaque/limited | Opaque | Opaque | Unsupported or reported |
| Modifiers | Role only | Role only | Role only | Target limitations reported |
| Variable layer height | Flag only | Flag only | Flag only | Target limitations reported |
| Textures | Core resources | Core resources | Core resources | Core resources preserved where supported |
