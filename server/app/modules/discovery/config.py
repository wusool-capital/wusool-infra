"""Typed application configuration, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root application settings. Instantiate via `get_settings()`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    slack_bot_token: str
    slack_signing_secret: str

    # Optional: local dev without a key just disables the lead search
    # (returns no leads) rather than requiring a key to boot — same
    # convention as matching_engine's own web fallback.
    firecrawl_api_key: str | None = None
    discovery_lead_search_limit: int = 3


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance."""
    return Settings()
