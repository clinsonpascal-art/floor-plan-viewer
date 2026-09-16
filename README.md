# LUXE Virtual Tour — V4 (procedural furnished tour)

An immersive, self-contained virtual tour built from a floor plan. No render
farm required: each room is drawn as a furnished, lit, perspective interior in
SVG, wired into a walk-through experience (drag-to-look, doorway transitions,
auto-tour, floor-plan minimap). Labeled as **AI Rendering & Visualization**.

Current demo unit: **1428 Brickell — Residence A** (2BR / 3BA, 11′ ceilings,
east / Biscayne Bay).

## Open it
Just open `dist/luxe_virtual_tour.html` in any browser. One file, no build,
no dependencies, no network calls. Deploy = drop that file (or embed the
`#app` block) on the page.

## Controls
- **Drag** the scene to look around; a gentle idle drift keeps it alive.
- **Tap a doorway pill** or a **room on the plan** to walk into it.
- **▶ TOUR** auto-walks all nine spaces like a walkthrough film.

## Structure
```
dist/
  luxe_virtual_tour.html   ← assembled, ready to ship
src/
  scene-engine.js          ← pure engine: perspective + furniture + room graph
  tour-template.html       ← viewer shell (HTML/CSS/DOM), token __ENGINE__
  build.py                 ← injects engine into template → dist/
  test-engine.js           ← node smoke test (builds every room)
INTEGRATION.md             ← manifest schema, photoreal drop-in, LUXE hooks
```

## Rebuild after editing
```
cd src
node test-engine.js        # verify all rooms build clean
python3 build.py           # regenerate dist/luxe_virtual_tour.html
```

## Where the geometry / furniture lives
`scene-engine.js`:
- **Projection** (`floorPt`, `pt3`, `box`) — one-point perspective helpers.
- **Furniture** (`sofa`, `island`, `bed`, `tub`, …) — procedural pieces placed
  on the floor plane. Edit these to restyle.
- **`ROOMS`** — the room graph: name, dimensions, view flag, adjacency
  (`links` = doorways), and minimap rectangle. This is the same shape as the
  V3 `manifest.json`, so it maps 1:1 onto the existing pipeline.
- **`buildRoomSVG(id)`** — assembles one room's scene.

## Honest scope
These interiors are elegant **vector** scenes — they read as a real place, but
they are not photographs. The path to true photoreal (matching the sample bay
render) is in `INTEGRATION.md`: the viewer already accepts a `panorama_url` per
room and will show that photo instead of the vector scene, same navigation.

## V5 reconstruction status
The backend now emits a `validation.json` artifact alongside the render package. It checks graph integrity and expected render/control artifacts, while deliberately leaving the actual floor-plan-to-image visual match as `manual_review_required`.


## V5 reconstruction note
The backend now exposes a structured room-geometry seam (boundary/walls/doors/windows/connections) for each generated room. Current Residence A geometry is an explicit reconstruction from the authored template, not a claim of exact extraction from the missing source floor plan. Exact floor-plan fidelity requires the original plan image/PDF/CAD.

## V5.1 source-plan grounding

`backend/source_continuum_residence_01.jpg` is the cropped first Tower Residence 01 sheet supplied during reconstruction. `backend/source_continuum_residence_01_annotated.jpg` shows the current approximate room/terrace mapping. The annotations are screenshot-grounded and explicitly not CAD-accurate.

## Continuum Residence 01 source-grounded reconstruction

The backend now includes a separate `continuum-residence-01` source graph based on the uploaded Continuum Tower Residence 01 plan. This graph is deliberately separate from the original 1428 Brickell demo template so the two floor plans are not conflated. See `backend/CONTINUUM_RECONSTRUCTION.md` for provenance and remaining fidelity work.

## Code delivery status

See `DELIVERY.md` for the implementation scope, source-fidelity notes, run commands, and live-provider configuration.
The repository is a working reconstruction of the floor-plan-to-tour pipeline; it is not claimed to be the original proprietary source.
