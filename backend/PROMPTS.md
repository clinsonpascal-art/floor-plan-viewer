# Production prompts

Every prompt the running service actually sends, quoted verbatim from source
so this document can never drift from what's deployed. Matches commit
`fe184153a7a9b573c031bd11b65584716931a28f`.

There are two categories:
1. **Image-generation prompts** (`app/prompts.py`) - sent to the OpenAI image
   model (`images.generate` / `images.edit`) to produce each room's photo.
2. **Vision-assist prompts** (`app/analyze.py`, `app/plan_parser.py`) - sent to
   the OpenAI vision model (`gpt-4o-mini` by default) to read printed text
   from an uploaded floor plan. These never generate images and never supply
   room geometry - see "No-hallucination guarantees" below.

## 1. Image generation (`app/prompts.py`)

### Design language (reused in every room)
```
Ultra-luxury Miami waterfront condominium interior in the Antonio Citterio idiom.
Polished large-format cream travertine floor, softly reflective, warm sunlight
streaking across it in long soft diagonals. Warm white plaster walls and ceiling,
flush recessed circular downlights, 11-foot ceilings. Restrained, editorial,
airy and bright — high-key natural daylight, gentle shadows, high dynamic range.
```

### Camera / quality (reused in every room)
```
Photorealistic architectural interior photograph for a luxury developer sales
gallery, architectural-digest quality. Shot on a full-frame camera with a 16-24mm
lens, eye-level, symmetrical composition, perfectly straight vertical lines,
ultra sharp, richly detailed.
```
```
No people, no text, no watermark, no logos, no signage. No fisheye distortion,
no tilted horizon, no clutter. Bright, clean and inviting — never dark or moody.
```

### View clause (rooms with a Biscayne Bay-facing wall)
```
A gently curved floor-to-ceiling glass curtain wall with slim aluminium mullions
opens to a wide Biscayne Bay view: calm turquoise water, low barrier islands and
the distant Miami skyline on the horizon, a soft golden sunrise low over the water
casting a bright reflection, a slim glass balcony railing just outside.
```

### Interior clause (rooms with no exterior view)
```
An interior room with no exterior view; a clean warm-white plaster feature wall
where the camera faces. Do not invent windows or a view the plan does not show.
```

### Per-room character (Residence A / Continuum authored rooms)
Each of these has a distinct "empty" and "staged" body text, e.g. kitchen:
```
empty:  A sleek kitchen with a large cream-stone waterfall island, fully integrated
        handleless walnut cabinetry, an Arclinea layout with Gaggenau cooktop and
        double oven, integrated refrigerator, and a wine cooler.
staged: The same kitchen with three slim brushed-brass pendants over the island
        and two low leather stools.
```
Full set of authored room ids: `great`, `kitchen`, `primary`, `pbath`, `bed2`,
`foyer`, `corridor`, `den`, `terrace` - see `ROOM_CHARACTER` in `app/prompts.py`
for every room's exact text.

### Generic room-type fallback (arbitrary/uploaded floor plans)
A room detected on an uploaded plan that isn't one of the authored ids above
gets a generic, type-appropriate body instead of a bare "A Room 3.":
```python
GENERIC_ROOM_TYPE_CHARACTER = {
    "kitchen": "A modern kitchen with an island, integrated cabinetry, stone countertops and stainless appliances.",
    "bathroom": "A modern bathroom with a vanity, mirror, and a tub or walk-in shower.",
    "bedroom": "A bright bedroom with a bed and nightstands, soft natural light.",
    "living": "A comfortable open living/great room with seating oriented toward the room's main light source.",
    "dining": "A dining area with a table sized to the room.",
    "foyer": "A welcoming entry foyer.",
    "corridor": "A clean hallway/corridor.",
    "den": "A quiet den / flex study room.",
    "outdoor": "An outdoor terrace/patio area.",
    "closet": "A built-in closet with shelving.",
    "utility": "A utility / laundry room with basic fixtures.",
    "garage": "A garage interior.",
    "unknown": "An interior room.",
}
```
Deliberately generic (no specific brand/fixture claims) since nothing is
actually known about an arbitrary uploaded room beyond its detected type.

### Assembled prompt (`build_prompt()` in `app/prompts.py`)
```
{CAMERA}
Subject: the {room_name} of a single luxury Miami residence, approximately {width_ft} by {length_ft} feet, 11-foot ceilings. {body}
{view_clause or interior_clause}
Style: {DESIGN_LANGUAGE}
{QUALITY}
```
The dimensions clause is only included when a real `width_ft`/`length_ft` is
known for that room - never a placeholder or invented figure.

### Structural control image
Each render is also conditioned on a depth/line-art control image built in
pure Python from the room's actual measured geometry (`app/geometry.py`,
sent via `images.edit`) - but **only when a real width/length is known**. If
no measurement exists for that room, no control image is generated and the
model falls back to unconditioned `images.generate` rather than being
constrained by a fabricated shape.

## 2. Vision-assist prompts (optional, require `OPENAI_API_KEY`)

These never invent room boundaries and never invent a dimension - they only
ever copy printed text that's actually legible in the image, or return null.

### `app/analyze.py::_VISION_PROMPT`
Used only for the two authored units (Residence A / Continuum), to refine
dimensions on top of the authored template - never to invent a room:
```
Analyze only the visible architectural floor plan. Return JSON:
{"rooms":[{"id":string,"width_ft":number|null,"length_ft":number|null}]}
Use these ids where present: great, kitchen, primary, pbath, bed2, bed3, bath2, bath3, powder, terrace. Copy dimensions only when printed and legible. Never invent.
```

### `app/plan_parser.py::_LABEL_PROMPT`
Used only for an arbitrary/uploaded floor plan, to label regions the
deterministic CV pipeline has ALREADY found (it is given exact pixel boxes
and asked only to read text near them - it is never asked to draw a box):
```
You are given an architectural floor plan image and a list of
already-detected room regions on that exact image, each with an index and its
exact pixel bounding box [x0,y0,x1,y1]. For each region, look ONLY at the
printed text inside or immediately touching that bounding box and report the
room name if one is legible there. Do not invent a name if none is printed or
legible in that region - use null. Do not add, remove, merge or move regions;
respond with exactly one entry per index, in the same order.
Regions: {regions}
Return strict JSON only: {"labels":[{"index":int,"name":string|null,"is_kitchen":bool,"is_bathroom":bool}]}
```

## No-hallucination guarantees

- Room **boundaries** for an uploaded/arbitrary plan always come from
  `app/plan_detect.py` (pure OpenCV/shapely geometry) - never from a vision
  or generative model, so a room shape can never be hallucinated.
- Room **dimensions** are `null` with `dimension_source: "not_available"`
  whenever no real scale reference exists for that plan - never a guessed
  or default size (`app/room_geometry.py`, `app/geometry.py`).
- Room **name/type** is an honest generic value (`"Room N"` /
  `"unknown"`) unless a printed label was actually read - never inferred
  from position or shape alone.
- `OPENAI_API_KEY` is read only via `os.getenv` at the two call sites above
  (`app/analyze.py`, `app/plan_parser.py`) and by the OpenAI SDK client
  itself (`app/providers/openai_provider.py`) - never hardcoded, never
  logged, never returned in any API response.
