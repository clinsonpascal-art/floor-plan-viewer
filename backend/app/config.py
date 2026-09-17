"""Runtime configuration. Everything is env-driven (prefix LUXE_)."""
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LUXE_", env_file=".env", extra="ignore")

    # provider: "mock" (offline, no key) | "openai" | "replicate"
    provider: str = "mock"

    openai_model: str = "gpt-image-1"     # image model
    vision_model: str = "gpt-4o-mini"     # plan analysis (openai provider only)
    replicate_model: str = ""             # e.g. black-forest-labs/flux-... (see BACKEND_TASKS)

    image_size: str = "1536x1024"         # landscape room still
    image_quality: str = "high"
    control_mode: str = "depth"           # depth | canny | none (structure control image)

    out_dir: str = "./renders"            # where images + manifests are written
    public_base: str = "/renders"         # URL prefix images are served under
    cors_origins: str = "*"
    api_key: str = ""                 # if set, X-API-Key is required
    job_db: str = "./luxe_jobs.sqlite3"
    job_workers: int = 1
    viewer_base: str = "/viewer"


settings = Settings()


def resolve_provider() -> str:
    """The provider actually used when a caller doesn't pin one explicitly.

    LUXE_PROVIDER, if set, always wins - an operator who explicitly asked for
    mock/replicate is never silently overridden. Otherwise, production should
    not stay on the mock renderer just because nobody flipped a setting after
    adding a real key: default to "openai" the moment OPENAI_API_KEY exists,
    else fall back to "mock"."""
    if os.getenv("LUXE_PROVIDER"):
        return settings.provider
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "mock"
