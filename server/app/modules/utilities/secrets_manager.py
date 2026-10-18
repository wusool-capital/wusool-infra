"""Settings base that reads the toolkit secret from AWS Secrets Manager.

Every module `Settings` extends `SecretsManagerSettings`, so local, dev and
prod share one code path: boto3's default credential chain (an AWS profile
locally, the instance role on EC2). Nothing secret lives in a `.env` file or
a rendered `.env.production`.

The secret is the same blob the EC2 bootstrap used to render: three
lowercase top-level keys plus an `env` map of ready-made variable names.
`ToolkitSecret.as_env_vars()` flattens it to variable names so the stock
`EnvSettingsSource` matching (prefixes, case, coercion) applies unchanged.

Precedence, highest first: init kwargs, process env, `.env`, the secret. A
secret edit therefore applies on the next process start, not live.
"""

from collections.abc import Mapping
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pydantic_settings.sources.utils import parse_env_vars

DEV_SECRET_ID = "/wusool/dev/toolkit"


class SecretLoadError(RuntimeError):
    """The toolkit secret could not be fetched or parsed."""


class ToolkitSecret(BaseModel):
    """Shape of `/wusool/<env>/toolkit`."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    database_url: str = ""
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    # Opaque map of ready-made env var names (ATTIO_API_KEY, ...).
    env: dict[str, str] = {}

    def as_env_vars(self) -> dict[str, str]:
        """Flatten to env var names; `env` entries win, as in the old bootstrap."""
        top_level = {
            "DATABASE_URL": self.database_url,
            "SLACK_BOT_TOKEN": self.slack_bot_token,
            "SLACK_SIGNING_SECRET": self.slack_signing_secret,
        }
        merged = {name: value for name, value in top_level.items() if value}
        merged.update(self.env)
        return merged


class SecretLocation(BaseSettings):
    """Which secret to read. An empty id disables the source (tests only)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_secrets_manager_secret_id: str | None = None
    aws_region: str = "eu-central-1"
    app_env: str = "development"

    @model_validator(mode="after")
    def default_to_dev_secret(self) -> "SecretLocation":
        """Fall back to the dev secret only in development, never silently in prod."""
        if self.aws_secrets_manager_secret_id is not None:
            return self
        if self.app_env != "development":
            raise ValueError("AWS_SECRETS_MANAGER_SECRET_ID is required unless APP_ENV=development")
        self.aws_secrets_manager_secret_id = DEV_SECRET_ID
        return self


@lru_cache
def fetch_toolkit_secret(secret_id: str, region: str) -> ToolkitSecret:
    """Fetch once per process; every Settings class shares the result."""
    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_id)
        return ToolkitSecret.model_validate_json(response["SecretString"])
    except (BotoCoreError, ClientError, ValueError, KeyError) as exc:
        raise SecretLoadError(
            f"Cannot load secret {secret_id!r} in {region}. Locally, run "
            "`aws sso login --profile wusool-sso` and set AWS_PROFILE=wusool-sso."
        ) from exc


class ToolkitSecretSource(EnvSettingsSource):
    """Env-style source backed by the cached toolkit secret."""

    def __init__(self, settings_cls: type[BaseSettings], location: SecretLocation) -> None:
        # `EnvSettingsSource.__init__` calls `_load_env_vars`, so this must be set first.
        self._location = location
        super().__init__(settings_cls)

    def _load_env_vars(self) -> Mapping[str, str | None]:
        secret_id = self._location.aws_secrets_manager_secret_id
        if not secret_id:
            return {}
        flat = fetch_toolkit_secret(secret_id, self._location.aws_region).as_env_vars()
        return parse_env_vars(
            flat, self.case_sensitive, self.env_ignore_empty, self.env_parse_none_str
        )


class SecretsManagerSettings(BaseSettings):
    """Base for every module `Settings`; the toolkit secret is the lowest-priority source."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            ToolkitSecretSource(settings_cls, SecretLocation()),
            file_secret_settings,
        )
