import json
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from app.modules.attio.config import AttioSettings
from app.modules.discovery.config import Settings as DiscoverySettings
from app.modules.utilities import secrets_manager
from app.modules.utilities.secrets_manager import (
    DEV_SECRET_ID,
    SecretLoadError,
    SecretLocation,
    ToolkitSecret,
    fetch_toolkit_secret,
)

SECRET_JSON = json.dumps(
    {
        "database_url": "postgresql://u:p@db/app",
        "slack_bot_token": "xoxb-secret",
        "slack_signing_secret": "sign-secret",
        "env": {"ATTIO_API_KEY": "attio-secret", "ATTIO_IS_TEST": "false"},
    }
)


_SECRET_ENV_NAMES = (
    "DATABASE_URL",
    "SLACK_BOT_TOKEN",
    "SLACK_SIGNING_SECRET",
    "ATTIO_API_KEY",
    "ATTIO_IS_TEST",
)


class _FakeClient:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def get_secret_value(self, *, SecretId: str) -> dict[str, str]:  # noqa: N803 - boto3 kwarg name
        self._calls.append(SecretId)
        return {"SecretString": SECRET_JSON}


@pytest.fixture
def fetch_calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    calls: list[str] = []
    monkeypatch.setattr(secrets_manager.boto3, "client", lambda *_a, **_k: _FakeClient(calls))
    monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "/wusool/test/toolkit")
    for name in _SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    fetch_toolkit_secret.cache_clear()
    yield calls
    fetch_toolkit_secret.cache_clear()


def test_as_env_vars_lets_env_map_win() -> None:
    secret = ToolkitSecret(database_url="a", env={"DATABASE_URL": "b", "X": "1"})
    assert secret.as_env_vars() == {"DATABASE_URL": "b", "X": "1"}


def test_as_env_vars_stringifies_scalars_and_skips_null() -> None:
    secret = ToolkitSecret.model_validate_json(
        '{"env": {"A_FLAG": true, "A_LIMIT": 5, "A_RATIO": 0.5, "GONE": null, "A_NAME": "x"}}'
    )
    expected = {"A_FLAG": "true", "A_LIMIT": "5", "A_RATIO": "0.5", "A_NAME": "x"}
    assert secret.as_env_vars() == expected


def test_validation_errors_do_not_echo_secret_values() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ToolkitSecret.model_validate_json('{"env": {"K": ["hunter2-secret-value"]}}')
    assert "hunter2" not in str(excinfo.value)


def test_settings_errors_do_not_echo_secret_values(
    fetch_calls: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATTIO_IS_TEST", "hunter2-not-a-bool")
    with pytest.raises(ValidationError) as excinfo:
        AttioSettings(_env_file=None)  # type: ignore[call-arg]
    assert "hunter2" not in str(excinfo.value)


def test_secret_fills_prefixed_and_unprefixed_fields(fetch_calls: list[str]) -> None:
    assert AttioSettings(_env_file=None).api_key == "attio-secret"  # type: ignore[call-arg]
    assert DiscoverySettings(_env_file=None).slack_bot_token == "xoxb-secret"  # type: ignore[call-arg]


def test_process_env_beats_secret(fetch_calls: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATTIO_IS_TEST", "true")
    assert AttioSettings(_env_file=None).is_test is True  # type: ignore[call-arg]


def test_secret_is_fetched_once_across_settings_classes(fetch_calls: list[str]) -> None:
    AttioSettings(_env_file=None)  # type: ignore[call-arg]
    DiscoverySettings(_env_file=None)  # type: ignore[call-arg]
    assert fetch_calls == ["/wusool/test/toolkit"]


def test_empty_secret_id_skips_aws(fetch_calls: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "")
    monkeypatch.setenv("ATTIO_API_KEY", "from-env")
    assert AttioSettings(_env_file=None).api_key == "from-env"  # type: ignore[call-arg]
    assert fetch_calls == []


def test_development_defaults_to_dev_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_SECRETS_MANAGER_SECRET_ID", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert SecretLocation(_env_file=None).aws_secrets_manager_secret_id == DEV_SECRET_ID  # type: ignore[call-arg]


def test_production_without_secret_id_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_SECRETS_MANAGER_SECRET_ID", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValueError, match="AWS_SECRETS_MANAGER_SECRET_ID"):
        SecretLocation(_env_file=None)  # type: ignore[call-arg]


def test_fetch_failure_names_the_login_step(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        def get_secret_value(self, **_k: str) -> dict[str, str]:
            raise ValueError("boom")

    monkeypatch.setattr(secrets_manager.boto3, "client", lambda *_a, **_k: _Boom())
    fetch_toolkit_secret.cache_clear()
    with pytest.raises(SecretLoadError, match="aws sso login"):
        fetch_toolkit_secret("/x", "eu-central-1")
    fetch_toolkit_secret.cache_clear()
