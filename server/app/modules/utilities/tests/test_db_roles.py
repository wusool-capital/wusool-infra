import json
from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.modules.utilities import db_roles, secrets_manager
from app.modules.utilities.db_roles import MasterSecret, admin_database_url, fetch_master_secret
from app.modules.utilities.secrets_manager import (
    SecretLoadError,
    ToolkitSecret,
    fetch_toolkit_secret,
)

# `%` and `@` are common in RDS-generated passwords and must survive URL handling.
TRICKY_PASSWORD = "p%40ss/w@rd:1"


class _FakeClient:
    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = payload

    def get_secret_value(self, *, SecretId: str) -> dict[str, str]:  # noqa: N803 - boto3 kwarg name
        return {"SecretString": json.dumps(self._payload)}


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    fetch_master_secret.cache_clear()
    fetch_toolkit_secret.cache_clear()
    yield
    fetch_master_secret.cache_clear()
    fetch_toolkit_secret.cache_clear()


def test_admin_url_keeps_host_and_database_and_swaps_login() -> None:
    master = MasterSecret(username="wusool_admin", password=TRICKY_PASSWORD)
    url = admin_database_url("postgresql://wusool_app:old@db.example:5433/wusool_crm", master)
    parsed = make_url(url)
    assert (parsed.host, parsed.port, parsed.database) == ("db.example", 5433, "wusool_crm")
    assert (parsed.username, parsed.password) == ("wusool_admin", TRICKY_PASSWORD)


def test_master_secret_ignores_extra_keys_and_hides_values_in_errors() -> None:
    assert (
        MasterSecret.model_validate_json('{"username":"u","password":"p","engine":"x"}').username
        == "u"
    )
    with pytest.raises(ValidationError) as excinfo:
        MasterSecret.model_validate_json('{"username":["hunter2-secret-value"],"password":"p"}')
    assert "hunter2" not in str(excinfo.value)


def test_fetch_master_secret_wraps_failures_without_the_cause_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db_roles.boto3, "client", lambda *_a, **_k: _FakeClient({"username": "u"}))
    with pytest.raises(SecretLoadError, match="master secret"):
        fetch_master_secret("arn:x", "eu-central-1")


def test_staged_app_password_is_never_an_env_var() -> None:
    secret = ToolkitSecret(app_db_password="staged-pw", database_url="postgresql://a:b@h/d")
    assert "staged-pw" not in secret.as_env_vars().values()


def test_main_skips_when_no_app_password_is_staged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "/wusool/test/toolkit")
    monkeypatch.setattr(
        secrets_manager.boto3, "client", lambda *_a, **_k: _FakeClient({"database_url": "x"})
    )
    with caplog.at_level("WARNING"):
        db_roles.main()
    assert "skipping" in caplog.text


def test_main_requires_the_master_secret_once_a_password_is_staged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "/wusool/test/toolkit")
    monkeypatch.delenv("DB_MASTER_SECRET_ARN", raising=False)
    monkeypatch.setattr(
        secrets_manager.boto3, "client", lambda *_a, **_k: _FakeClient({"app_db_password": "pw"})
    )
    with pytest.raises(SystemExit, match="DB_MASTER_SECRET_ARN"):
        db_roles.main()


def test_unsafe_role_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unsafe"):
        db_roles._require_identifier("x; DROP TABLE organizations")
