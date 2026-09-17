# LUXE API reference

Live deployment: `https://ideal-trust-production-50d9.up.railway.app`
Matches commit `fe184153a7a9b573c031bd11b65584716931a28f` on `origin/master`.

All examples below were run against the live deployment and are known to work.

## Auth

If `LUXE_API_KEY` is set on the server, send it as `X-API-Key` on every
`/api/v1/*` request. The legacy `/units`, `/jobs` routes and `/health` never
require it. The currently deployed instance has no API key configured.

## Health / status

```bash
curl https://ideal-trust-production-50d9.up.railway.app/health
```
```json
{
  "ok": true,
  "provider": "openai",
  "model": "gpt-image-1",
  "api_version": "v1",
  "authentication": false,
  "openai_key_configured": true,
  "railway_environment": "production",
  "railway_service": "ideal-trust",
  "railway_deployment_id": "...",
  "railway_git_commit": "..."
}
```
`provider` reports what will *actually* be used for a job that doesn't pin a
provider explicitly - it automatically becomes `"openai"` once
`OPENAI_API_KEY` is configured (see `app/config.py::resolve_provider`).

## The core flow: any floor plan → photoreal room images

This is the primary integration surface for Alex's ask: a viewer selects or
uploads **any** floor plan (not just the two pre-authored demo units) and
gets back detected rooms with photorealistic renders.

### 1. Create a project
```bash
curl -X POST https://ideal-trust-production-50d9.up.railway.app/api/v1/projects \
  -F "name=Client Portal Upload"
```
```json
{"project_id": "26c1c5311482443c", "name": "Client Portal Upload", "status": "created"}
```

### 2. Upload the floor plan
```bash
curl -X POST https://ideal-trust-production-50d9.up.railway.app/api/v1/projects/{project_id}/floor-plan \
  -F "file=@floorplan.jpg;type=image/jpeg" \
  -F "total_interior_sqft=2080"
```
```json
{"project_id": "...", "input_id": "2a15a6030cbd44b89e1f29f5fcb3dfa3", "filename": "floorplan.jpg", "status": "uploaded"}
```
Accepted formats: JPG, PNG, WEBP.

`total_interior_sqft` is optional but **strongly recommended** - it's the one
number that lets the deterministic pipeline produce real room dimensions for
a plan with no OCR-legible printed dimension text (which is most real-world
listing floor plans). Without it, and without legible printed dimension text,
every room's `width_ft`/`depth_ft` stay `null` with
`"dimension_source": "not_available"` - honest, but unmeasured. With it,
rooms get a real (if lower-confidence, area-derived)
`"dimension_source": "estimated_from_total_area_low_confidence"` measurement,
which also then constrains the generated image via a real structural control
image (see PROMPTS.md). Must be a positive number; a listing's already-known
total square footage is normally exactly what you'd pass here. Can also be
supplied later, at job-creation time (step 3), if it wasn't known at upload
time - see below.

### 3. Start generation
```bash
curl -X POST https://ideal-trust-production-50d9.up.railway.app/api/v1/projects/{project_id}/jobs \
  -F "input_id={input_id}"
```
```json
{"job_id": "d6d5df0cb909", "project_id": "...", "status": "pending", "idempotent_reuse": false, "status_url": "/api/v1/jobs/d6d5df0cb909"}
```
Optional form fields:
- `unit_id` - use a known authored template (`residence-a`, `continuum-residence-01`) instead of analyzing the upload
- `staged` - `true`/`false`, lightly furnished vs. empty-architectural render style
- `only` - comma-separated room ids to generate a subset (useful for cheap testing)
- `provider` - force `mock` / `openai` / `replicate`; omit to auto-select the real provider when a key is configured
- `total_interior_sqft` - same scale reference as step 2, for when it wasn't supplied at upload time (does not overwrite an existing value if omitted here)
- `webhook_url` - receives a completion/error callback
- `Idempotency-Key` header - retrying the same key returns the existing job instead of creating a duplicate

### 4. Poll for completion
```bash
curl https://ideal-trust-production-50d9.up.railway.app/api/v1/jobs/{job_id}
```
`status` is one of `pending`, `running`, `done`, `error`. A real (non-mock)
job generating several rooms can take several minutes - this is genuine
image-generation time, not a stuck job.

### 5. Retrieve results
```bash
curl https://ideal-trust-production-50d9.up.railway.app/api/v1/jobs/{job_id}/manifest   # everything
curl https://ideal-trust-production-50d9.up.railway.app/api/v1/jobs/{job_id}/geometry   # detected walls/rooms/dimensions per room
curl https://ideal-trust-production-50d9.up.railway.app/api/v1/jobs/{job_id}/rooms      # room graph + navigation order
curl https://ideal-trust-production-50d9.up.railway.app/api/v1/jobs/{job_id}/assets     # {room_id, type, url} for every rendered image
curl https://ideal-trust-production-50d9.up.railway.app/api/v1/jobs/{job_id}/viewer     # embeddable tour viewer URL
```

Each room in the manifest includes, among other fields:
```json
{
  "name": "Room 1",
  "room_type": "unknown",
  "dimension_source": "not_available",
  "geometry": {
    "width_ft": null,
    "depth_ft": null,
    "source_fidelity": "dimensions_not_available_no_geometry_generated",
    "source_polygon_px": [[211, 432], [429, 432], [422, 362], [263, 362], [214, 395]]
  },
  "panorama_url": "/renders/{project_id}/room_1.jpg"
}
```
`width_ft`/`depth_ft` are `null` and `dimension_source` is `"not_available"`
whenever no real scale reference (a manual reference, printed dimension
text, or a known total floor area) was found for that plan - the pipeline
never fabricates a measurement. `room_type` is `"unknown"` unless a printed
label was legible (directly, or via the optional vision-assist step when a
key is configured).

## Known-unit shortcuts (legacy routes, no upload needed)

For the two pre-authored demo units, generation can be triggered directly
without the project/upload steps:
```bash
curl -X POST https://ideal-trust-production-50d9.up.railway.app/units/residence-a/generate \
  -F "staged=false"
curl -X POST https://ideal-trust-production-50d9.up.railway.app/units/continuum-residence-01/generate \
  -F "staged=false"

curl https://ideal-trust-production-50d9.up.railway.app/jobs/{job_id}
curl https://ideal-trust-production-50d9.up.railway.app/units/{unit_id}/manifest
curl https://ideal-trust-production-50d9.up.railway.app/units/{unit_id}/validate
```
`residence-a` (9 rooms) and `continuum-residence-01` (10 rooms, 5 of which
are real photographs used as fixed overrides rather than generated - see
`app/static_room_images.py`) both use hand-authored layout templates, not
the deterministic upload-analysis path.

## Viewer

```
GET /viewer/{unit_id}?job_id={job_id}
```
Serves the bundled virtual-tour frontend pre-loaded with that job's actual
rooms/panoramas. Omit `job_id` to fall back to the most recently generated
manifest on disk for that unit.

## Verified real-provider runs (this deployment)

- `residence-a`, all 9 rooms, `provider: "openai"`, `validation: "pass"` - every room actually generated (no static overrides for this unit).
- `continuum-residence-01`, all 10 rooms, `provider: "openai"`, `validation: "pass"` - 5 real photographs (Living Room, Kitchen, Primary Bedroom, Primary Bath, Terrace) plus 5 newly generated (Bedroom 2, Bedroom 3, Bath 2, Bath 3, Powder Room).
- A synthetic 2-room test plan through the full upload → analyze → detect → generate flow, `provider: "openai"` auto-selected with no provider override in the request.

Generated images were downloaded and visually confirmed as genuine
photorealistic renders (PNG-format bytes from the OpenAI API, ~2-2.5MB each -
the mock provider always produces small JPEG-format gradient placeholders
with "MOCK RENDER" burned into the image, so this is easy to tell apart).
