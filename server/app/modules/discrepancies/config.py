"""Typed application configuration, loaded from environment variables / .env.
No `database_url` — this module has no persistence layer; it reads buyer
criteria through `BuyerCriteriaReaderPort`, wired at startup by `server/main.py`.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    slack_bot_token: str
    slack_signing_secret: str

    aws_region: str = "eu-central-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    # Same field name and default `matching_engine`/`enrichment` already
    # declare — every module's root `Settings` reads unprefixed env vars
    # (see `lead_magnets/config.py`'s docstring on this), so sharing the
    # name is only safe because all three want the same value: this
    # module's one Bedrock call (extracting criteria from the advisor's note)
    # needs no separate, larger model than extraction already uses.
    aws_bedrock_model_id_extraction: str = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"

    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
