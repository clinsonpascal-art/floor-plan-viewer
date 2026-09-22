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

# The finish, reused verbatim in every room so the whole unit reads as ONE home.
# Lighting-independent: floor/wall/ceiling materials only - the light itself
# (and the exterior sky/water it implies) comes from LIGHTING below, per room.
DESIGN_LANGUAGE = (
    "Ultra-luxury Miami waterfront condominium interior in the Antonio Citterio idiom. "
    "Polished large-format cream travertine floor, softly reflective. Warm white plaster "
    "walls and ceiling, flush recessed circular downlights, 11-foot ceilings. Restrained, "
    "editorial architectural photography."
)

# Selectable lighting/daylight conditions (client-facing viewpoint control).
# "mood": the interior light description (every room, view or not).
# "sky": the exterior sky/water/skyline description (view rooms only, spliced
# into view_clause()). Keep these paired so a room's interior light and its
# visible exterior light always agree with each other.
# "atmosphere": a location-agnostic version of "sky" - light/color/reflection
# only, no Miami/Biscayne Bay nouns - used by get_view_clause() so the same
# daylight condition can drive ANY waterfront_type/city, not just the fixed
# Biscayne Bay scene "sky" describes. "mood"/"sky" are unchanged so view_clause()
# and every existing caller/test keep producing byte-identical output.
DEFAULT_LIGHTING = "daylight"
LIGHTING = {
    "sunrise": {
        "mood": "Soft early-morning light, long warm-gold shadows streaking across the floor, "
                "gentle low-angle sun, high dynamic range.",
        "sky": "a soft golden sunrise low over the water, calm turquoise-to-rose water, the "
               "Miami skyline silhouetted on the horizon, a bright warm reflection on the glass",
        "atmosphere": "a soft golden sunrise light, calm low-angle glow, a bright warm reflection "
                      "on the glass",
    },
    "daylight": {
        "mood": "Bright even midday daylight, high-key natural light, crisp soft shadows, "
                "high dynamic range.",
        "sky": "a clear bright midday sky, calm turquoise water, the Miami skyline sharp on "
               "the horizon in full sun",
        "atmosphere": "a clear bright midday light, crisp full-sun clarity",
    },
    "sunset": {
        "mood": "Warm late-afternoon light, long amber shadows, golden-hour glow across the "
                "floor and walls.",
        "sky": "a warm orange-and-pink sunset over the water, the Miami skyline backlit in "
               "silhouette, a warm reflection on the glass",
        "atmosphere": "a warm orange-and-pink sunset glow, golden-hour light, a warm reflection "
                      "on the glass",
    },
    "evening": {
        "mood": "Blue-hour interior, warm recessed downlights on, soft ambient glow, dim "
                "natural light through the glass.",
        "sky": "a deep blue dusk sky over the water, the Miami skyline lit with warm window "
               "lights, a calm dark reflection on the glass",
        "atmosphere": "a deep blue dusk light, distant lights beginning to glow, a calm dark "
                      "reflection on the glass",
    },
    "night": {
        "mood": "Nighttime interior, warm recessed downlights fully on, soft pools of warm "
                "light, dark windows.",
        "sky": "a dark night sky over the water, the Miami skyline glittering with lights, "
               "a still black reflection on the glass",
        "atmosphere": "a dark night sky, distant lights glittering, a still black reflection "
                      "on the glass",
    },
}


def view_clause(lighting: str) -> str:
    """View rooms: the curved bay glass, with the exterior sky/water/skyline
    driven by the requested lighting condition. NOTE: the generic
    water/skyline description here is a placeholder pending the property's
    actual Section 3 (THE VIEW) stack/floor content - not yet replaced
    (tracked separately, out of scope for the lighting feature itself)."""
    sky = LIGHTING[lighting]["sky"]
    return (
        "A gently curved floor-to-ceiling glass curtain wall with slim aluminium mullions "
        f"opens to a wide Biscayne Bay view: {sky}, a slim glass balcony railing just outside."
    )


# --- Dynamic outlook system (waterfront_type / city / direction / floor) ---
# Kept separate from the lighting/daylight feature above, and from any real
# property's actual view content - this is a generic, reusable clause
# generator driven only by the caller's parameters, never a hardcoded or
# invented specific view.

WATERFRONT_TYPES = {
    "oceanfront": "the open ocean stretching to a wide horizon",
    "bayfront": "a wide bay of calm open water",
    "intracoastal": "the Intracoastal Waterway, calm channel water with docks and a low "
                    "landscaped shoreline",
    "urban_skyline": "the city skyline",
}
DEFAULT_WATERFRONT_TYPE = "bayfront"
DEFAULT_CITY = "Miami"

# Floor elevation bands: (min_floor, max_floor_inclusive_or_None_for_open_ended, clause).
FLOOR_ELEVATION_BANDS = (
    (1, 15, "a lower-level outlook over the surrounding tree canopy and neighboring rooftops"),
    (16, 35, "an open mid-level vista across open water with a clear horizon"),
    (36, None, "a sweeping high-altitude outlook over a deep, distant horizon"),
)

_DIRECTION_ALIASES = {
    "n": "north", "ne": "northeast", "e": "east", "se": "southeast",
    "s": "south", "sw": "southwest", "w": "west", "nw": "northwest",
}


def _elevation_clause(floor) -> str | None:
    """None/non-integer/below band 1 -> no elevation clause, never an error."""
    try:
        floor = int(floor)
    except (TypeError, ValueError):
        return None
    for lo, hi, text in FLOOR_ELEVATION_BANDS:
        if floor >= lo and (hi is None or floor <= hi):
            return text
    return None


def _direction_word(direction: str | None) -> str | None:
    """Normalizes common compass abbreviations/casing; an unrecognized but
    non-empty value is still used verbatim rather than dropped, so a caller's
    direction always affects the output."""
    if not direction or not direction.strip():
        return None
    key = direction.strip().lower()
    return _DIRECTION_ALIASES.get(key, key)


def get_view_clause(daylight: str | None = None, waterfront_type: str | None = None,
                    city: str | None = None, direction: str | None = None,
                    floor=None) -> str:
    """Reusable, parameterized outlook system (Requirement 1).

    Every argument is optional. Passing none of waterfront_type/city/direction/
    floor reproduces view_clause()'s exact existing text, so build_prompt()
    callers that only ever passed `lighting` are completely unaffected.
    Unknown waterfront_type/daylight values fall back to a default rather than
    raising, same tolerance already used for LIGHTING elsewhere in this module.
    """
    daylight = daylight if daylight in LIGHTING else DEFAULT_LIGHTING
    if waterfront_type is None and city is None and direction is None and floor is None:
        return view_clause(daylight)

    wf = waterfront_type if waterfront_type in WATERFRONT_TYPES else DEFAULT_WATERFRONT_TYPE
    city_name = city or DEFAULT_CITY
    atmosphere = LIGHTING[daylight]["atmosphere"]

    if wf == "urban_skyline":
        subject = f"{WATERFRONT_TYPES[wf]} of {city_name}"
    else:
        subject = f"{WATERFRONT_TYPES[wf]}, the {city_name} skyline visible on the horizon"

    direction_word = _direction_word(direction)
    direction_frag = f", facing {direction_word}" if direction_word else ""

    elevation_text = _elevation_clause(floor)
    elevation_frag = f" — {elevation_text}" if elevation_text else ""

    return (
        "A gently curved floor-to-ceiling glass curtain wall with slim aluminium mullions "
        f"opens to {subject}{direction_frag}{elevation_frag}: {atmosphere}, "
        "a slim glass balcony railing just outside."
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
                "empty": "A wraparound outdoor terrace in warm stone paving, a full-height glass railing, open to Biscayne Bay beyond.",
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


def build_prompt(room_id, room_name, width_ft=None, length_ft=None, view=None, staged=False,
                  room_type=None, lighting=None, waterfront_type=None, city=None,
                  direction=None, floor=None):
    """lighting: one of LIGHTING's keys (sunrise/daylight/sunset/evening/night).
    Unknown or omitted falls back to DEFAULT_LIGHTING - never a KeyError, and
    every existing caller that doesn't pass it gets exactly today's daylight
    look, unchanged.

    waterfront_type/city/direction/floor: the dynamic outlook system
    (Requirement 1, see get_view_clause()). Omitting all four reproduces
    today's fixed Biscayne Bay view exactly - existing callers are
    unaffected."""
    lighting = lighting if lighting in LIGHTING else DEFAULT_LIGHTING
    if room_id in ROOM_CHARACTER:
        char = ROOM_CHARACTER[room_id]
    else:
        body = GENERIC_ROOM_TYPE_CHARACTER.get(room_type, f"A {room_name}.")
        char = {"view": bool(view), "empty": body, "staged": body}
    is_view = char.get("view", bool(view))
    dims = f"approximately {width_ft:g} by {length_ft:g} feet, " if width_ft and length_ft else ""
    body = char["staged" if staged else "empty"]
    view_text = (get_view_clause(daylight=lighting, waterfront_type=waterfront_type, city=city,
                                 direction=direction, floor=floor)
                if is_view else INTERIOR_CLAUSE)
    return (f"{CAMERA}\n"
            f"Subject: the {room_name} of a single luxury Miami residence, {dims}"
            f"11-foot ceilings. {body}\n"
            f"{view_text}\n"
            f"Style: {DESIGN_LANGUAGE} {LIGHTING[lighting]['mood']}\n"
            f"{QUALITY}")
