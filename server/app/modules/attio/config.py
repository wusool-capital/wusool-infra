"""Typed Attio configuration, loaded from environment variables / .env —
independent of `ddl_commands`' own `Settings` (which reads the same
`ATTIO_API_KEY` env var for its own settings object, plus
`ATTIO_WEBHOOK_SECRET` for its `/webhooks/attio` route, which stays in
`ddl_commands` and isn't this module's concern) so this module has no
import-time dependency back on its one consumer.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Attio settings. Instantiate via `get_settings()`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DEV Attio workspace write access — same value crm-sync's PowerShell
    # scripts already use (DEV_ATTIO_API_KEY), confirmed write-capable.
    attio_api_key: str


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance."""
    return Settings()
