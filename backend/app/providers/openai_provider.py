"""Live photoreal path using OpenAI image generation/editing."""

import base64
import os
from pathlib import Path

from ..config import settings


class OpenAIProvider:
    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set")

        from openai import OpenAI
        self.client = OpenAI()

    def generate(self, prompt: str, size: str, control=None) -> bytes:
        if control is not None:
            if isinstance(control, (str, Path)):
                with open(control, "rb") as image_file:
                    res = self.client.images.edit(
                        model=settings.openai_model,
                        image=image_file,
                        prompt=prompt,
                        size=size,
                        quality=settings.image_quality,
                        input_fidelity="high",
                    )
            else:
                res = self.client.images.edit(
                    model=settings.openai_model,
                    image=("floor_plan.jpg", control, "image/jpeg"),
                    prompt=prompt,
                    size=size,
                    quality=settings.image_quality,
                    input_fidelity="high",
                )
        else:
            res = self.client.images.generate(
                model=settings.openai_model,
                prompt=prompt,
                size=size,
                quality=settings.image_quality,
            )

        return base64.b64decode(res.data[0].b64_json)