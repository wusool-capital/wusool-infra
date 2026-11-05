"""Settings for the Google Workspace connection.

The bare name `google_service_account_json` is deliberate: one key serves
every consumer, so it is not prefixed with any one module. The value lives in
Secrets Manager, never in `.env`.
"""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from app.modules.google_workspace.providers.google.auth import ServiceAccountKey
from app.modules.utilities import SecretsManagerSettings


class GoogleWorkspaceSettings(SecretsManagerSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_service_account_json: str | None = None

    def service_account_key(self) -> ServiceAccountKey | None:
        """None when no key is configured, so callers can stay switched off."""
        if not self.google_service_account_json:
            return None
        return ServiceAccountKey.model_validate_json(self.google_service_account_json)


@lru_cache
def get_settings() -> GoogleWorkspaceSettings:
    return GoogleWorkspaceSettings()
