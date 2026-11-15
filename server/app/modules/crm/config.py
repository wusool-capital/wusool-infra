"""Settings for the CRM role API. Only the database it reads."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import SettingsConfigDict

from app.modules.utilities import SecretsManagerSettings
from app.modules.utilities.domain.database_url import asyncpg_url


class CrmSettings(SecretsManagerSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Ensure the URL uses the asyncpg driver scheme regardless of input form."""
        return asyncpg_url(value)


@lru_cache
def get_settings() -> CrmSettings:
    return CrmSettings()
