"""Slack app credentials for Sign in with Slack. The same variables other modules
read; declared here so `auth` never depends on a consumer's settings."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from app.modules.utilities import SecretsManagerSettings


class AuthSettings(SecretsManagerSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    slack_bot_token: str
    slack_client_id: str | None = None
    slack_client_secret: SecretStr | None = None


@lru_cache
def get_settings() -> AuthSettings:
    return AuthSettings()


class AccessSettings(SecretsManagerSettings):
    """Cloudflare Access in front of the Engine. Unset leaves the Engine API off."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Bare host, e.g. `wusoolcapital.cloudflareaccess.com`.
    cf_access_team_domain: str | None = None
    cf_access_engine_aud: str | None = None


@lru_cache
def get_access_settings() -> AccessSettings:
    return AccessSettings()
