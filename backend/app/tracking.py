"""Thin tracking seam. Defaults to log mode for staging, like the rest of LUXE.
Wire `_emit` to the real LUXE tracking system. Remember to add these unit3d_*
types to the platform's _ALLOWED_TYPES before shipping (open item from NC notes)."""
import logging

log = logging.getLogger("luxe.tracking")

ALLOWED_PREFIX = "unit3d_"   # unit3d_room_enter, unit3d_tour_start, unit3d_generate, ...


def track(event: str, data: dict | None = None) -> bool:
    if not event.startswith(ALLOWED_PREFIX):
        log.warning("dropped non-allowed tracking event: %s", event)
        return False
    _emit(event, data or {})
    return True


def _emit(event: str, data: dict):
    # TODO: replace with the real LUXE tracking call.
    log.info("TRACK %s %s", event, data)
