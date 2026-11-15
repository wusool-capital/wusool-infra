"""Wusool MCP settings. Unset `MCP_PUBLIC_URL` or `MCP_TOKEN_SECRET` leaves `/mcp`
unmounted rather than serving it half-configured."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import SettingsConfigDict

from app.modules.utilities import SecretsManagerSettings
from app.modules.utilities.domain.database_url import asyncpg_url


class McpSettings(SecretsManagerSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", env_file=".env", extra="ignore")

    # Base URL Claude reaches the Toolkit on, e.g. https://tools.wusoolcapital.com.
    public_url: str | None = None
    # Signs every client id, code and token; rotating it signs everyone out.
    token_secret: SecretStr | None = None
    calls_per_hour: int = Field(default=600, gt=0)


class McpDatabaseSettings(SecretsManagerSettings):
    """Only the database the tool-call audit writes to."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Ensure the URL uses the asyncpg driver scheme regardless of input form."""
        return asyncpg_url(value)


@lru_cache
def get_settings() -> McpSettings:
    return McpSettings()


@lru_cache
def get_database_settings() -> McpDatabaseSettings:
    return McpDatabaseSettings()
