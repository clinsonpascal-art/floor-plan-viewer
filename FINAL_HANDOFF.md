# LUXE — Final Code Handoff

## What this package is

A working reconstruction of the floor-plan-to-room-render-to-tour pipeline demonstrated by the supplied LUXE video and grounded against the supplied Continuum Tower Residence 01 floor-plan screenshot.

## Quickest Windows test

1. Extract this ZIP.
2. Open `scripts/run_continuum_demo.bat`.
3. The script creates a Python virtual environment, installs dependencies, runs the offline Continuum pipeline, then starts FastAPI.
4. Open `http://127.0.0.1:8000/health` to verify the API.

## Direct backend test

```powershell
cd backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH="."
$env:LUXE_PROVIDER="mock"
python -m pytest -q
python -m app.pipeline --unit continuum-residence-01 --plan .\source_continuum_residence_01.jpg
```

## Live photoreal generation

The repository intentionally contains no API credentials. Set the required provider environment variables on the deployment machine, then run the same pipeline. The offline mock provider is included so the complete code path can be tested without spending API credits.

## Important scope

The Continuum input supplied for reconstruction is a screenshot. Room regions are source-grounded and source-shaped, but exact CAD/survey-level wall and opening coordinates are not claimed. Generated JPGs are still room views, not true 360-degree equirectangular panoramas.

## Updated API contract

The backend now includes a versioned `/api/v1` integration surface for project creation, floor-plan uploads, queued jobs, status polling, structured geometry, rooms, assets, manifest retrieval and viewer access. API-key authentication, idempotency keys, durable SQLite job metadata and optional webhooks are included. See `backend/README.md` and `backend/BACKEND_TASKS.md`.

The generic new-floor-plan path uses the configured OpenAI vision model to parse visible rooms and legible printed dimensions. It requires `OPENAI_API_KEY`; the supplied Continuum plan remains available for offline mock testing.
