"""Environment-driven settings (pydantic-settings). Prefix: REVIEW_LENS_."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from review_lens.models import Lens, Severity

DEFAULT_MODEL = "claude-opus-4-8"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REVIEW_LENS_", extra="ignore")

    #: Anthropic key. Read from ANTHROPIC_API_KEY (not the REVIEW_LENS_ prefix)
    #: because that's the conventional name the SDK and every CI already use.
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    model: str = DEFAULT_MODEL
    max_tokens: int = 4096
    lenses: list[Lens] = Field(default_factory=lambda: list(Lens))
    verify: bool = True
    min_severity: Severity = Severity.LOW
    min_confidence: float = 0.5
