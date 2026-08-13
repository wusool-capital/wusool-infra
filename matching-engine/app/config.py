"""Typed application configuration, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoringSettings(BaseSettings):
    """Weights applied when deterministically calculating match scores."""

    model_config = SettingsConfigDict(env_prefix="SCORING_WEIGHT_", extra="ignore")

    strategy: float = 0.4
    size: float = 0.3
    sector: float = 0.3


class ConfidenceSettings(BaseSettings):
    """Multipliers applied when calculating data confidence for a match."""

    model_config = SettingsConfigDict(env_prefix="CONFIDENCE_", extra="ignore")

    missing_field_penalty: float = 0.1
    stale_data_penalty: float = 0.15


class Settings(BaseSettings):
    """Root application settings. Instantiate via `get_settings()`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str

    slack_bot_token: str
    slack_signing_secret: str

    anthropic_api_key: str
    llm_model_extraction: str
    llm_model_reasoning: str

    stage3_top_n: int = 3

    scoring: ScoringSettings = Field(default_factory=ScoringSettings)
    confidence: ConfidenceSettings = Field(default_factory=ConfidenceSettings)

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
