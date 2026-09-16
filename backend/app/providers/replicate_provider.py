"""Structure-faithful path: Flux/SDXL + depth/edge ControlNet via Replicate.

This is the upgrade that makes the photo obey the actual plan geometry, using the
per-room control image from geometry.control_for_room(). Set:
    REPLICATE_API_TOKEN=r8_...
    LUXE_REPLICATE_MODEL=<a depth-ControlNet model, e.g. a Flux depth variant>
    LUXE_CONTROL_MODE=depth        # match the model (depth vs canny)

NOTE: input key names vary per model (`control_image`, `image`, `control`, and
`guidance` vs `guidance_scale`). Confirm against your chosen model's schema and
adjust the two marked lines. Everything else is done.
"""
import base64
import os

import httpx

from ..config import settings


class ReplicateProvider:
    def __init__(self):
        if not os.getenv("REPLICATE_API_TOKEN"):
            raise RuntimeError("REPLICATE_API_TOKEN not set")
        if not settings.replicate_model:
            raise RuntimeError("LUXE_REPLICATE_MODEL not set (a depth/edge ControlNet)")
        import replicate  # lazy
        self._replicate = replicate
        self.model = settings.replicate_model

    def generate(self, prompt: str, size: str, control: bytes | None = None) -> bytes:
        w, h = (size.split("x") + ["1024"])[:2]
        inputs = {
            "prompt": prompt,
            "width": int(w), "height": int(h),
            "num_inference_steps": int(os.getenv("LUXE_STEPS", "28")),
            "guidance": float(os.getenv("LUXE_GUIDANCE", "3.5")),   # <-- some models: guidance_scale
            "output_format": "jpg",
        }
        if control:
            data_uri = "data:image/png;base64," + base64.b64encode(control).decode()
            inputs["control_image"] = data_uri                     # <-- some models: image / control
        out = self._replicate.run(self.model, input=inputs)
        return self._to_bytes(out)

    @staticmethod
    def _to_bytes(out) -> bytes:
        item = out[0] if isinstance(out, (list, tuple)) else out
        if hasattr(item, "read"):          # replicate FileOutput
            return item.read()
        url = getattr(item, "url", None) or (item if isinstance(item, str) else None)
        if url:
            return httpx.get(url, timeout=180).content
        raise RuntimeError("unexpected replicate output type")
