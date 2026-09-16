# Backend handoff — API status

## What is now implemented

- Versioned REST API under `/api/v1` with FastAPI-generated OpenAPI docs at `/docs`.
- Project creation and floor-plan upload/reference flow.
- Background processing queue with durable SQLite job metadata.
- Job status polling with structured errors.
- Idempotency via `Idempotency-Key` per project.
- Optional API-key authentication via `LUXE_API_KEY`.
- Optional webhook callback on job completion/error.
- Geometry, rooms, assets, manifest and viewer endpoints.
- Backward-compatible `/units/...` and `/jobs/...` demo routes.
- Generic uploaded-plan analysis path for new units using OpenAI vision; no silent fallback to Residence A.
- Known Continuum Residence 01 source-grounded path remains available and offline-testable with the mock provider.

## Verified locally in this handoff

- Existing regression suite passes.
- Versioned API contract test passes authentication, project creation, upload, idempotent job creation, background execution, status, geometry, rooms, assets and viewer endpoints.
- Mock provider requires no API key.

## Production integration items

1. Set a real `LUXE_API_KEY` and HTTPS reverse proxy in the deployment environment.
2. Set `OPENAI_API_KEY` for generic floor-plan parsing and live image generation, or configure a compatible Replicate model for structure-conditioned generation.
3. Replace the single-process SQLite/thread queue with the production worker/Redis stack if LUXE needs multi-instance horizontal scaling.
4. Restrict webhook destinations and add platform-specific authentication/signing if LUXE provides a webhook standard.
5. The current generated room assets are still images. They are exposed through the existing viewer compatibility field but are not true 360° equirectangular panoramas.
6. Raster floor plans still produce inferred geometry/openings; CAD/vector input is required for construction-grade coordinates.
