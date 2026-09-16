"""Image provider seam. Swap providers without touching the pipeline."""
from typing import Optional, Protocol


class ImageProvider(Protocol):
    def generate(self, prompt: str, size: str, control: Optional[bytes] = None) -> bytes:
        """Return encoded image bytes (JPEG/PNG). `control` is an optional
        depth/edge image for structure-faithful models (ignored by text-to-image)."""
        ...


def get_provider(name: str) -> ImageProvider:
    name = (name or "mock").lower()
    if name == "mock":
        from .mock import MockProvider
        return MockProvider()
    if name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider()
    if name == "replicate":
        from .replicate_provider import ReplicateProvider
        return ReplicateProvider()
    raise ValueError(f"unknown provider: {name}")
