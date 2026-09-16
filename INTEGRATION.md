# Integration & upgrade path

## 1. Room graph = manifest
`ROOMS` in `scene-engine.js` is the drop-in equivalent of a
`data/renders/<unit>/manifest.json`. Each entry:

```js
great: {
  name: "Great Room",
  dim:  "18′ × 15′4″",
  view: true,                 // true = bay glass wall; false = interior back wall
  feat: "…",                  // caption shown in the info chip
  x, y, w, h,                 // minimap rectangle (140 × 162 schematic)
  links: [                    // doorways = tour adjacency
    { to: "kitchen", label: "Kitchen", px: 88, py: 42, chev: "→" }
  ]
}
```
To drive it from the real manifest, replace the literal `ROOMS`/`ORDER` with a
fetch of the unit manifest and map fields across. The viewer code needs no
other change.

## 2. Photoreal drop-in (the upgrade to sample quality)
The viewer already branches per room:

```js
function sceneHTML(id){
  var r = ROOMS[id];
  if (r.panorama_url)                    // ← real AI-generated 360° pano
    return '<div class="pano" style="background-image:url('+r.panorama_url+')"></div>';
  return buildRoomSVG(id);              // ← procedural vector fallback
}
```

So the moment a room has a `panorama_url`, the tour shows a photograph with the
same drag-look and doorway navigation. Rollout can be **per room** — publish
the great room photoreal while the rest stay vector.

### Producing the panos (rendering/API side)
Reuse the existing floor-plan analysis/extract step, then generate a **depth-guided** 360°
pano per room so the photo obeys the real geometry (window/door positions,
ceiling height, island placement) instead of inventing them:

1. `analyze(plan)` → rooms, dimensions, fixtures (already implemented in this repo).
2. Render each room's shell as a **depth / line pass** (cheap; the
   geometry model already exists in `geometry.py`).
3. Feed that pass as structural control into an image model (depth-conditioned
   generation) → photoreal equirectangular pano; bake water/skyline outside the
   glass as the house standard.
4. Write `panorama_url` into the manifest; keep `status: review_required` so a
   human approves before publish.

## 3. Platform integration hooks
The viewer keeps a single integration seam:

- **Tracking** — uncomment the `LUXE_TRACKING.track("unit3d_room_enter", …)`
  call in `go()`. Remember to add the `unit3d_*` event types to your
  tracking allow-list before shipping.
- **Registration gate** — if your platform requires a registration/gating
  step before showing the tour, wrap the initial `mount()` behind that check
  (e.g. a `LUXE_REGISTRATION.resolve(...)`-style call) the same way any other
  gated widget on your platform does.
- **Multi-unit** — the file is unit-agnostic once `ROOMS` comes from a manifest;
  pass a `floor_plan_id` and fetch that unit's graph.

## 4. What this replaces
The rotating `<model-viewer>` GLB ("match box") is no longer the customer-facing
surface. Keep the Blender geometry — it becomes the **depth source** for the
photoreal step, not the thing buyers look at.
