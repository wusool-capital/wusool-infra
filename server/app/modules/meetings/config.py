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

    # Desktop app authenticates its transcript pushes with this shared key —
    # required, so a misconfigured deploy fails fast rather than accepting
    # unauthenticated writes.
    desktop_api_key: str

    # AWS Bedrock. Access key/secret are optional: the standard AWS
    # credential provider chain (IAM role, ECS/EC2 task role, local profile,
    # env) applies when unset.
    aws_region: str = "eu-central-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_bedrock_model_id: str = "eu.anthropic.claude-sonnet-4-6"

    summary_max_tokens: int = 8192
    summary_max_tokens_per_chunk: int = 8000
    max_concurrent_summaries: int = 1
    max_transcript_chars: int = 1_500_000

    # The unified "note" object exists only in SOURCE Attio today (mirrors
    # ddl_commands' ATTIO_NOTE_OBJECT_SLUG — same env var, both classes use
    # extra="ignore" so reading it in two Settings classes is safe). Leave
    # unset to skip pushing notes to Attio entirely.
    attio_note_object_slug: str | None = None

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
