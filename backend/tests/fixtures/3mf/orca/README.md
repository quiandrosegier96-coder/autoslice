# Orca fixtures required

No real OrcaSlicer fixture is available. Orca support must not be certified until these files are supplied with redistribution permission.

## Required first fixture: `orca_basic.3mf`

- source slicer/version: unknown until supplied
- printer/nozzle/material: unknown until supplied
- plates: expected 1, must be verified
- objects: expected at least 1, must be verified
- materials/tools: unknown
- special features: plain object and project settings
- expected detection: `orca`, threshold derived from observed evidence

## Required coverage fixtures

- `orca_multi_object.3mf`: multiple named objects, components/instances and transforms
- `orca_multi_plate.3mf`: at least two populated plates
- `orca_multicolor.3mf`: explicit material/tool and painting assignments
- `orca_modifier.3mf`: modifier geometry with object-specific settings
- `orca_supports.3mf`: blocker, enforcer and painted/organic support data

For every file record slicer version, printer, nozzle, materials, plate/object counts, expected mappings and special metadata in this document or a same-named sidecar Markdown file.
