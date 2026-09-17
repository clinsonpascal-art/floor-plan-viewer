"""
Prompt engine tuned to the LUXE sample: an empty ultra-luxury Miami condo room
with a gently curved floor-to-ceiling glass wall, polished cream stone floor with
sunlight streaking across it, high-key natural light, and a Biscayne Bay sunset.

Two levers carry the quality:
  1. DESIGN_LANGUAGE — reused in every room so the whole unit reads as ONE home.
  2. CAMERA + QUALITY — force real-estate / sales-gallery realism.

Staging: EMPTY (default, matches the sample) or STAGED (lightly furnished).
Consistency tip for the engineer: fix one seed and keep DESIGN_LANGUAGE identical
across rooms so finishes match unit-wide.
"""

# The finish, reused verbatim in every room — this is what makes it one residence.
DESIGN_LANGUAGE = (
    "Ultra-luxury Miami waterfront condominium interior in the Antonio Citterio idiom. "
    "Polished large-format cream travertine floor, softly reflective, warm sunlight "
    "streaking across it in long soft diagonals. Warm white plaster walls and ceiling, "
    "flush recessed circular downlights, 11-foot ceilings. Restrained, editorial, "
    "airy and bright — high-key natural daylight, gentle shadows, high dynamic range."
)

# View rooms: the curved bay glass from the sample.
VIEW_CLAUSE = (
    "A gently curved floor-to-ceiling glass curtain wall with slim aluminium mullions "
    "opens to a wide Biscayne Bay view: calm turquoise water, low barrier islands and "
    "the distant Miami skyline on the horizon, a soft golden sunrise low over the water "
    "casting a bright reflection, a slim glass balcony railing just outside."
)
INTERIOR_CLAUSE = (
    "An interior room with no exterior view; a clean warm-white plaster feature wall "
    "where the camera faces. Do not invent windows or a view the plan does not show."
)

CAMERA = (
    "Photorealistic architectural interior photograph for a luxury developer sales "
    "gallery, architectural-digest quality. Shot on a full-frame camera with a 16-24mm "
    "lens, eye-level, symmetrical composition, perfectly straight vertical lines, "
    "ultra sharp, richly detailed."
)
QUALITY = (
    "No people, no text, no watermark, no logos, no signage. No fisheye distortion, "
    "no tilted horizon, no clutter. Bright, clean and inviting — never dark or moody."
)

# Per-room: the space + its hero feature. EMPTY stays architectural; STAGED adds
# restrained furniture.
ROOM_CHARACTER = {
    "great":   {"view": True,
                "empty": "An expansive open great room, entirely empty, the curved bay glass filling the far wall, sunlight pooling on the bare polished floor.",
                "staged": "An expansive great room with a single low-profile linen sectional and a sculptural stone coffee table on a soft wool rug, oriented toward the curved bay glass."},
    "kitchen": {"view": False,
                "empty": "A sleek kitchen with a large cream-stone waterfall island, fully integrated handleless walnut cabinetry, an Arclinea layout with Gaggenau cooktop and double oven, integrated refrigerator, and a wine cooler.",
                "staged": "The same kitchen with three slim brushed-brass pendants over the island and two low leather stools."},
    "primary": {"view": True,
                "empty": "A serene primary bedroom, empty, calm bay light through the curved floor-to-ceiling glass, bare polished floor.",
                "staged": "A serene primary bedroom with a low upholstered platform bed, two walnut nightstands and a bench at the foot, facing the bay glass."},
    "pbath":   {"view": False,
                "empty": "A spa-like primary bathroom with a sculptural freestanding stone soaking tub, a floating dual walnut vanity with a backlit mirror, and full-height book-matched stone walls.",
                "staged": "The same bathroom with neatly rolled towels and a single white orchid."},
    "bed2":    {"view": True,
                "empty": "A bright, empty second bedroom, bay light through the curved glass, bare polished floor.",
                "staged": "A bright second bedroom with a low upholstered bed and two walnut nightstands."},
    "foyer":   {"view": False,
                "empty": "A private entry foyer, empty, a wide double-door entry and a clean warm-white feature wall, soft downlight on the polished floor.",
                "staged": "The foyer with a slim walnut console and a large framed mirror."},
    "corridor":{"view": False,
                "empty": "A calm gallery corridor, empty, clean warm-white walls and an even run of recessed ceiling downlights receding to a bright end.",
                "staged": "The gallery corridor with a long low runner and a slim console."},
    "den":     {"view": False,
                "empty": "A quiet den / study, empty, clean warm-white walls, soft even light.",
                "staged": "A den with a walnut desk, a single reading chair and low integrated shelving."},
    "terrace": {"view": True,
                "empty": "A wraparound outdoor terrace in warm stone paving, a full-height glass railing, wide open Biscayne Bay and a golden sunrise beyond.",
                "staged": "The terrace with two low chaise lounges and a summer-kitchen counter along the wall."},
}


# Fallback body text for a room from an arbitrary/uploaded plan that has no
# authored ROOM_CHARACTER entry. Generic staging appropriate to the room TYPE
# only (e.g. "a kitchen has an island and cabinetry") - never a specific
# brand/fixture claim, since nothing is actually known about this room beyond
# its detected type and measurements.
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


def build_prompt(room_id, room_name, width_ft=None, length_ft=None, view=None, staged=False, room_type=None):
    if room_id in ROOM_CHARACTER:
        char = ROOM_CHARACTER[room_id]
    else:
        body = GENERIC_ROOM_TYPE_CHARACTER.get(room_type, f"A {room_name}.")
        char = {"view": bool(view), "empty": body, "staged": body}
    is_view = char.get("view", bool(view))
    dims = f"approximately {width_ft:g} by {length_ft:g} feet, " if width_ft and length_ft else ""
    body = char["staged" if staged else "empty"]
    view_clause = VIEW_CLAUSE if is_view else INTERIOR_CLAUSE
    return (f"{CAMERA}\n"
            f"Subject: the {room_name} of a single luxury Miami residence, {dims}"
            f"11-foot ceilings. {body}\n"
            f"{view_clause}\n"
            f"Style: {DESIGN_LANGUAGE}\n"
            f"{QUALITY}")
