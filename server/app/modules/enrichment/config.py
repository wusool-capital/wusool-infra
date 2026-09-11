"""Typed application configuration, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root application settings. Instantiate via `get_settings()`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str

    slack_bot_token: str
    slack_signing_secret: str

    aws_region: str = "eu-central-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_bedrock_model_id_extraction: str = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"

    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096

    # Research: optional since local dev without a key just disables
    # enrichment's research step (fails soft, proposes nothing) rather than
    # requiring a key to boot.
    firecrawl_api_key: str | None = None

    # Structured company-data waterfall (seller targets only — see
    # EnrichMixin._structured_lookup), tried in this order before the
    # Firecrawl+LLM fallback. Both optional: missing either key just skips
    # that tier rather than requiring it to boot.
    diffbot_api_key: str | None = None
    people_data_labs_api_key: str | None = None

    # Values below this confidence are dropped before ever reaching the
    # operator's confirmation dialog — not a scoring input, a proposal gate.
    enrichment_min_confidence: float = 0.6

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Ensure the URL uses the asyncpg driver scheme regardless of input form."""
        if value.startswith("postgresql+asyncpg://"):
            return value
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance."""
    return Settings()
