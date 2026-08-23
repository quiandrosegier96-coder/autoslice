# Universal AutoSlice 1.5.63 — release candidate notes

Status: **unreleased / blocked by real-fixture certification**

## Included

- Universal3MF detection, parsing, semantic preservation, translation and validated Anycubic export.
- Deterministic project, geometry, printability, orientation, support, placement and optimization intelligence.
- Unified analyze/convert pipeline snapshots with traceable recommendations and stage timings.
- AutoSlice workflow in the existing Tools UI with preserve/autoslice modes, diagnostics, fallback and validated download.
- Owner-scoped upload, analysis, conversion and download workflows.
- Streamed proxy uploads, bounded archive/XML handling, timeouts, isolated workspaces and retention cleanup.
- Dependency security updates for Next.js, Electron, FastAPI, Starlette, Pytest and JWT handling.

## Security changes

- Removed client-controlled upload paths and unsafe legacy ZIP extraction.
- Enforced true streamed upload limits and cleanup of partial uploads.
- Added UUID validation and authenticated job ownership checks.
- Removed verification codes, reset links, email addresses and output filenames from release-path logs.
- Replaced vulnerable `python-jose`/`ecdsa` with PyJWT for the existing HS256 contract.
- Removed known npm and Python dependency advisories reported during the audit.
- Electron now provisions a private local JWT secret instead of depending on an external environment value.

## Compatibility

- Frontend, backend and Electron versions are aligned at 1.5.63.
- The legacy conversion route remains available and is the default rollout path.
- Universal3MF remains behind `USE_UNIVERSAL_3MF_ENGINE` until real vendor fixture acceptance is complete.
- Only Anycubic is a production-writable target.

## Validation summary

- Backend: 304 passed, 26 explicitly skipped for missing real vendor fixtures.
- Frontend: 7 tests passed, TypeScript passed, production build passed.
- Dependency audits: zero known frontend, Electron and Python findings after updates.
- Eight-way conversion concurrency isolation passed.
- Synthetic small, medium, large, multicolor and multi-object benchmarks completed.

## Release blocker

The repository lacks the real Bambu, Anycubic, Orca, Prusa and Cura fixtures required by its own acceptance tests. Consequently the Universal engine is not enabled by default and this candidate must not be tagged, pushed or promoted to production.
