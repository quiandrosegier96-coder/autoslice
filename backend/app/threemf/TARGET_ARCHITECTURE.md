# Universal target architecture

Production conversion always follows:

`secure container -> detector -> source parser -> Universal3MF -> translation plan -> translation -> target exporter -> target validator -> target parser`

Source parsers do not import exporters. Exporters do not inspect source slicer identity. A target is enabled only when its exporter and target validator are registered centrally.

## Current target matrix

No real slicer-generated fixtures are present, so no route is certified as fully tested.

| Source | Anycubic | Orca | Prusa | Cura |
|---|---:|---:|---:|---:|
| Bambu | `~` implemented, fixture-unverified | `?` | `?` | `?` |
| Orca | `~` implemented, fixtures missing | `?` | `?` | `?` |
| Prusa | `~` implemented, fixtures missing | `?` | `?` | `?` |
| Cura | `~` implemented, fixtures missing | `?` | `?` | `?` |

Legend: `~` partial/limited, `?` not implemented. A check mark requires a real fixture and successful validation/reparse test.

## Adding a target

Add and register:

1. target capability profile;
2. `ThreeMFExporter` implementation;
3. `TargetValidator` implementation;
4. target parser/detection evidence if not already available;
5. licensed fixtures and semantic roundtrip/cross-slicer tests.

Orca, Prusa and Cura exporters are intentionally absent. Their real package metadata, settings serialization, multi-plate and material conventions cannot be inferred safely from the current fixture inventory.
