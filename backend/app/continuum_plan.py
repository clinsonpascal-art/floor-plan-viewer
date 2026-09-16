"""Source-plan annotations for the uploaded Continuum Tower Residence 01 sheet.

The supplied image is a screenshot, not CAD.  These annotations therefore preserve
what can be grounded in the visible plan: room names, approximate pixel regions and
terrace locations.  They are deliberately not presented as survey/CAD coordinates.
"""
from __future__ import annotations

# Coordinates refer to the cropped first plan page, 810 x 490 px, produced from the
# uploaded screenshot.  x/y increase right/down.  Regions are approximate visual
# room extents and are useful for control/mapping, not construction documentation.
PLAN_SIZE = [810, 490]

RESIDENCE_01_SOURCE_ROOMS = {
    "bed2": {"source_label": "BEDROOM 2", "bbox_px": [392, 155, 480, 276], "polygon_px": [[392,155],[480,155],[480,276],[392,276]]},
    "great": {"source_label": "LIVING ROOM", "bbox_px": [480, 155, 638, 280], "polygon_px": [[480,155],[638,155],[638,280],[480,280]]},
    "kitchen": {"source_label": "KITCHEN", "bbox_px": [515, 280, 640, 355], "polygon_px": [[515,280],[640,280],[640,355],[515,355]]},
    "primary": {"source_label": "PRIMARY BEDROOM", "bbox_px": [640, 275, 800, 390], "polygon_px": [[640,275],[800,275],[800,390],[640,390]]},
    "bed3": {"source_label": "BEDROOM 3", "bbox_px": [235, 275, 355, 365], "polygon_px": [[235,275],[355,275],[355,365],[235,365]]},
    "bath2": {"source_label": "BATH 2", "bbox_px": [450, 275, 515, 355], "polygon_px": [[450,275],[515,275],[515,355],[450,355]]},
    "bath3": {"source_label": "BATH 3", "bbox_px": [395, 350, 455, 425], "polygon_px": [[395,350],[455,350],[455,425],[395,425]]},
    "powder": {"source_label": "POWDER ROOM", "bbox_px": [455, 370, 515, 445], "polygon_px": [[455,370],[515,370],[515,445],[455,445]]},
    "pbath": {"source_label": "PRIMARY BATH", "bbox_px": [600, 390, 800, 458], "polygon_px": [[600,390],[800,390],[800,458],[600,458]]},
}


RESIDENCE_01_TERRACES = {
    "terrace_a": {"source_label": "PRIVATE TERRACE (A/C)", "bbox_px": [220, 150, 390, 275], "polygon_px": [[220,150],[390,150],[390,275],[220,275]]},
    "terrace_b": {"source_label": "TERRACE B", "bbox_px": [390, 95, 640, 155], "polygon_px": [[390,95],[640,95],[640,155],[390,155]]},
    "terrace_c": {"source_label": "TERRACE C", "bbox_px": [640, 95, 800, 275], "polygon_px": [[640,95],[800,95],[800,275],[640,275]]},
}

SOURCE_SUMMARY = {
    "building": "CONTINUUM CLUB & RESIDENCES",
    "residence": "Tower Residence 01",
    "floors": "7-23",
    "bedrooms": 3,
    "baths": "3.5",
    "interior_sf": 2080,
    "exterior_sf": 1000,
    "total_sf": 3080,
}
