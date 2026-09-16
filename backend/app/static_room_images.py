"""Static real-photo overrides for specific rooms, keyed by (unit_id, room_id).

These are real photographs (cropped video-frame stills, overlay UI removed -
see backend/static/stock_photos/) used in place of a generated render for a
small, explicit set of rooms. Every other room in every other unit is
unaffected and keeps using the normal image-generation pipeline.

Paths are relative to backend/static/.
"""
STATIC_ROOM_IMAGES: dict[str, dict[str, str]] = {
    "continuum-residence-01": {
        "great": "stock_photos/LUXE_Living_Room.jpg",
        "kitchen": "stock_photos/LUXE_Kitchen.jpg",
        "terrace": "stock_photos/LUXE_Patio.jpg",
        "primary": "stock_photos/LUXE_Bedroom.jpg",
        "pbath": "stock_photos/LUXE_Bathroom.jpg",
    }
}
