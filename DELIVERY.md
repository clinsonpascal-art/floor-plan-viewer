# LUXE Residence Tour — Code Delivery

## What is delivered

This repository contains a working reconstruction of the LUXE floor-plan-to-tour pipeline.
It is intentionally presented as a reconstruction, not as the recovered original proprietary source.

### Pipeline

`floor plan -> source room mapping -> room graph -> room geometry -> structural control -> image provider -> validation -> tour manifest`

### Implemented

- FastAPI render service
- Background job API
- Unit/room templates
- Continuum Tower Residence 01 source-plan mapping
- Per-room source-plan crops
- Room-local wall/door/window geometry model
- Depth/line-art control image generation in pure Python
- Mock provider for offline testing
- OpenAI photoreal provider
- Replicate structure-conditioned provider seam
- Per-room prompts and design language
- Manifest / rooms.js / panoramas.js generation
- Deterministic artifact validation
- Static image serving
- LUXE tracking seam
- Existing self-contained virtual-tour frontend
- Regression tests for the original Residence A demo and the supplied Continuum plan

## Source fidelity

The supplied Continuum plan is a screenshot. The source-grounded annotations therefore use approximate pixel regions.
They are useful for reconstruction and visualization, but are not CAD or construction measurements.

The code records this provenance in `source_plan` and `geometry` instead of presenting inferred values as exact.

## Run offline

From `backend/`:

```bash
pip install -r requirements.txt
PYTHONPATH=. LUXE_PROVIDER=mock python tests/test_smoke.py
PYTHONPATH=. pytest -q
```

## Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

Then submit a generation request to:

`POST /units/{unit_id}/generate`

For the supplied Continuum source plan, use:

`unit_id=continuum-residence-01`

and upload the plan as the `file` form field.

## Live image generation

Set:

```bash
export OPENAI_API_KEY=...
```

`LUXE_PROVIDER=openai` no longer needs to be set by hand - the API
automatically switches from the mock renderer to the real OpenAI provider
the moment `OPENAI_API_KEY` is present (see `resolve_provider()` in
`backend/app/config.py`). Set `LUXE_PROVIDER` explicitly only to force a
specific provider regardless of a configured key. See `backend/API.md` for
the full endpoint reference and `backend/PROMPTS.md` for every prompt used
in production.

For structure-conditioned generation, configure the Replicate provider and a compatible model in:

```bash
export LUXE_PROVIDER=replicate
export REPLICATE_API_TOKEN=...
export LUXE_REPLICATE_MODEL=...
```

The exact Replicate input names depend on the selected model; the provider isolates that integration point.

## Important scope note

The generated `.jpg` files are still-image room views. They are exposed through the tour's `panorama_url` field for compatibility with the existing viewer, but they are not true 360-degree equirectangular panoramas.

A Matterport-style 360 walk-around system would require a separate equirectangular generation/stitching and navigation layer.

## Current reconstruction boundary

The supplied Continuum screenshot is used as source evidence and source-shaped room geometry. Exact wall/opening coordinates are not represented as CAD because the supplied asset is a raster screenshot. The provider layer is ready for live generation, but live credentials are intentionally not included.
