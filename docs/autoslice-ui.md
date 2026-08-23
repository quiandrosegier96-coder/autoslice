# AutoSlice Tools UI

Step 17 exposes the Universal3MF pipeline in the existing **Tools** navigation entry. The route is `/tools`; the existing Hinged Box Generator remains available at `/tools/hinged-box` and is linked from the Tools header.

## User flow

1. Upload or drop one `.3mf` file.
2. The existing upload and project-analysis APIs detect the source family and show project facts.
3. Select the writable target, printer, nozzle, nozzle material, filament and `PRESERVE` or `AUTOSLICE` mode.
4. Run the dry-run Universal3MF analysis.
5. Review compatibility, printability, geometry, support, orientation, placement, diagnostics and recommendations.
6. Convert when the backend has not returned a blocking condition.
7. Review pipeline stage status and download only validated Universal3MF output.

The UI supports Bambu, Orca, Prusa, Cura, Anycubic and generic/core 3MF input through the backend detector/parser registry. “Any file” means any valid 3MF variant understood with sufficient detector confidence; unknown or malformed archives are rejected safely. The target selector currently exposes Anycubic because that is the only production-writable target registered by Step 16.

## API boundary

The frontend performs no geometry, compatibility, support, orientation, placement or optimization calculations. It displays the contracts returned by:

- `POST /api/upload`
- `GET /api/analyze/{job_id}`
- `POST /api/universal-analyze`
- `POST /api/universal-convert`
- `GET /api/universal-convert/{conversion_id}/download`

Shared TypeScript contracts live in `frontend/src/lib/autoslice-types.ts`. Recommendation rows retain the backend `setting`, `old_value`, `new_value`, `reason`, `rule` and `confidence` fields. A blocking printability status or blocking optimization diagnostic disables conversion.

## Progress and validation

The conversion card shows analyzing, optimizing, exporting and validating. Completed backend pipeline stages and their measured durations are displayed after the conversion response. The download action is enabled only when `validation_passed` is true. This is completion-stage reporting, not server-pushed live progress; a future streaming job API can provide finer live status without changing analysis logic in the client.

## Legacy fallback

If Universal3MF conversion is unavailable, the UI can use the existing explicit legacy conversion endpoint. It immediately displays:

> Universal conversion unavailable — legacy compatibility route used.

Legacy output is downloaded directly because that API does not expose the Universal3MF validation/download contract. It is never represented as a universally validated result.

## States and responsive behavior

The tool includes empty, drag, uploading, detected, analyzing, ready, converting, done, blocked and failed states. Failure cards include retry. The two-column desktop layout collapses to a single column on smaller screens and uses the existing Tailwind colors, borders, typography and spacing.

## Tests

`npm test` covers file acceptance, analysis prerequisites, target selection, recommendation traceability, blocking conversion, fallback messaging and output filename generation. `npm run lint` type-checks the complete frontend integration. Backend runtime tests continue to validate the API and Universal3MF pipeline contracts.
