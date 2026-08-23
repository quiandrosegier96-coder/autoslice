# Cura 3MF format analysis

Status: fixture-unverified.

The repository contains no real Cura-generated `.3mf`. The implementation therefore relies only on core 3MF semantics plus conservative evidence from Cura's public setting vocabulary. It recognizes multiple independent signals (Cura application metadata plus Cura metadata part or relationship) and never treats a filename alone as proof.

Semantically mapped when explicitly present:

- core objects, meshes, components, build items and transforms;
- common Cura setting keys such as `wall_line_count`, `infill_sparse_density`, `speed_print`, `material_print_temperature` and `support_enable`;
- explicit per-object `extruder_nr` as a physical tool assignment, separate from material identity;
- known Cura mesh roles (`infill_mesh`, `cutting_mesh`, support blocker/enforcer roles).

All Cura metadata package parts remain source-only opaque in Universal3MF. They are not copied blindly into another target format.

Not established without fixtures:

- definitive metadata part names and schema variants across Cura versions;
- printer/extruder stack serialization;
- material profile identity and colors;
- multipart grouping, plate/build extensions and modifier targeting;
- sufficient target project structure for a Cura exporter or validator.

Primary references reviewed:

- UltiMaker Cura source repository: https://github.com/Ultimaker/Cura
- 3MF Core Specification: https://github.com/3MFConsortium/spec_core

A Cura exporter must not be registered until authentic Cura output can validate and reparse with semantic fixture assertions.
