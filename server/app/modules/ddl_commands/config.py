"""Typed application configuration, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root application settings. Instantiate via `get_settings()`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Read by nothing. The dev/prod split that actually matters is
    # `attio.config.ATTIO_IS_TEST`, which is deliberately independent of
    # environment naming — don't wire CRM behaviour to this.
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str

    slack_bot_token: str
    slack_signing_secret: str

    # SOURCE Attio workspace write access. One workspace serves both
    # environments; `attio.config.ATTIO_IS_TEST` is what separates them.
    # `/edit-seller`/`/edit-buyer` write to Attio first, then Postgres, in
    # the same request — see `ddl_commands/shared/attio/`.
    attio_api_key: str

    # Signs inbound Attio webhook deliveries (`POST /webhooks/attio`) —
    # returned once by Attio in the response to `POST /v2/webhooks`, never
    # retrievable again after that. See `ddl_commands/shared/attio/signature.py`.
    attio_webhook_secret: str

    # The unified "note" object's api_slug in SOURCE Attio. Constant since
    # one SOURCE workspace began serving both environments; kept
    # configurable only so a slug rename doesn't need a code change.
    attio_note_object_slug: str = "note"

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
