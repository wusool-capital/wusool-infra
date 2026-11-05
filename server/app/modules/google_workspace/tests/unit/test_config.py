import pytest
from pydantic import ValidationError

from app.modules.google_workspace.config import GoogleWorkspaceSettings

KEY_JSON = (
    '{"type": "service_account", "client_email": "reader@proj.iam.gserviceaccount.com",'
    ' "private_key": "pem", "private_key_id": "kid-1", "client_id": "123"}'
)


def test_no_key_means_the_connection_stays_off() -> None:
    assert GoogleWorkspaceSettings(google_service_account_json=None).service_account_key() is None
    assert GoogleWorkspaceSettings(google_service_account_json="").service_account_key() is None


def test_the_key_is_parsed_from_the_secret_json() -> None:
    key = GoogleWorkspaceSettings(google_service_account_json=KEY_JSON).service_account_key()

    assert key is not None
    assert key.client_email == "reader@proj.iam.gserviceaccount.com"
    assert key.private_key_id == "kid-1"


def test_a_malformed_key_fails_loudly_without_echoing_the_secret() -> None:
    settings = GoogleWorkspaceSettings(google_service_account_json='{"private_key": "SECRET-PEM"}')

    with pytest.raises(ValidationError) as caught:
        settings.service_account_key()

    assert "SECRET-PEM" not in str(caught.value)
