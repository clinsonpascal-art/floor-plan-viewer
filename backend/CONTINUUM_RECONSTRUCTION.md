# Continuum Residence 01 — source-grounded reconstruction

## Source

The source is the uploaded screenshot of **CONTINUUM CLUB & RESIDENCES — Tower Residence 01**, Floors 7–23.
The sheet states 3 bedrooms, 3.5 baths, a private terrace, 2,080 SF interior, 1,000 SF exterior and 3,080 SF total.

## Grounded room graph

The visible plan supports these named interior spaces:

- Bedroom 2
- Living Room
- Kitchen
- Primary Bedroom
- Primary Bath
- Bath 2
- Bedroom 3
- Bath 3
- Powder Room

The plan also shows three terrace zones labelled A/C, B and C. The reconstruction groups these into one customer-facing `Private Terrace` node while preserving the source labels in the source annotation module.

## Geometry provenance

The source screenshot is not CAD. Room regions are represented by annotated pixel bounding boxes and are therefore **approximate visual regions**. Room-local 3D shells are inferred from those regions and the printed total interior area; they are not construction dimensions.

Every generated room carries:

- `source_plan.bbox_px`
- `source_plan.label`
- `geometry.source_polygon_px`
- `geometry.source_fidelity`
- `geometry.dimension_provenance`
- a reviewable `<room>.plan.png` source crop
- a structural `<room>.control.png` control image

## Important distinction

The pipeline now reconstructs from the supplied Continuum plan instead of using the earlier 1428 Brickell Residence A room template. The older `residence-a` demo remains intact for regression testing.

The remaining fidelity step is to replace screenshot-region approximations with traced wall centerlines / polygons and explicit door/window coordinates. That requires either a higher-resolution source, CAD/PDF vector data, or a manual tracing/review pass.
