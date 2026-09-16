# LUXE Residence Render Service

Floor plan → photoreal room images → files the virtual tour reads. Runs offline
on a mock provider; going live is a config flip to `openai` (or `replicate` for
structure-faithful). See **BACKEND_TASKS.md** for the finish checklist + time
estimates.

## Quick start
```
pip install -r requirements.txt
LUXE_PROVIDER=mock PYTHONPATH=. python tests/test_smoke.py   # end-to-end, no key
uvicorn app.main:app --reload
```

## Go live (photoreal)
```
export LUXE_PROVIDER=openai
export OPENAI_API_KEY=sk-...
uvicorn app.main:app
# POST /units/residence-a/generate   (form: staged, only, provider, file?)
# GET  /jobs/{job_id}                 poll to "done"
# GET  /units/residence-a/manifest
```

## Structure-faithful renders (Phase B)
Each room gets an eye-level **control image** (depth or lineart) built in pure
Python from the plan dimensions — no Blender. Preview them:
```
PYTHONPATH=. python -m app.geometry ./control_preview
```
Set `LUXE_CONTROL_MODE=depth|canny|none`. With `LUXE_PROVIDER=replicate` +
`LUXE_REPLICATE_MODEL`, the control image is sent to a depth/edge ControlNet so
the photo obeys the room's proportion, ceiling height and window wall. Each run
also saves `<room>.control.png` beside the render for review.

## Layout
```
app/
  config.py         env-driven settings
  prompts.py        design language + per-room prompts  ← main tuning surface
  analyze.py        per-unit layout template + optional vision dim refinement
  geometry.py       eye-level depth/lineart control-image renderer (pure Python)
  providers/        mock | openai | replicate(stub)
  pipeline.py       orchestration (+ CLI: python -m app.pipeline)
  jobs.py           background job store
  tracking.py       LUXE unit3d_* seam
  main.py           FastAPI app
tests/test_smoke.py end-to-end on mock provider
```

## Wire into the tour
Generation writes `renders/<unit>/rooms.js` + `panoramas.js`. Include both before
the tour script (or fetch `/units/<unit>/manifest` and set `window.LUXE_ROOMS`/
`window.LUXE_PANOS`). The tour renders photos with the same doorways, minimap and
auto-tour; rooms without a photo fall back to the vector scene.

## Versioned API (production-shaped contract)

The service exposes a stable `/api/v1` REST surface for integration:

- `POST /api/v1/projects` — create a project
- `POST /api/v1/projects/{project_id}/floor-plan` — upload a floor plan and receive an `input_id`
- `POST /api/v1/projects/{project_id}/jobs` — enqueue processing (`input_id`, optional `unit_id`, `staged`, `only`, `provider`, `webhook_url`)
- `GET /api/v1/jobs/{job_id}` — durable job status and result metadata
- `GET /api/v1/jobs/{job_id}/geometry` — structured room geometry
- `GET /api/v1/jobs/{job_id}/rooms` — room graph and navigation order
- `GET /api/v1/jobs/{job_id}/assets` — generated room asset URLs
- `GET /api/v1/jobs/{job_id}/viewer` — embeddable viewer route
- `GET /api/v1/jobs/{job_id}/manifest` — complete manifest

If `LUXE_API_KEY` is set, clients send `X-API-Key`. `Idempotency-Key` prevents a client retry from creating a duplicate job for the same project. Jobs are recorded in SQLite and executed by a single-process worker queue; this can be replaced by Redis/Celery without changing the API contract. Optional `webhook_url` receives completion/error callbacks.

For an unregistered/new floor plan, supply `unit_id` only when you have a known layout template. Otherwise the live OpenAI vision parser analyzes the uploaded plan and creates the room list from the visible plan. A live `OPENAI_API_KEY` is required for that generic path.
