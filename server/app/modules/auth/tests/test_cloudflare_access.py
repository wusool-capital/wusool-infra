import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.modules.auth.config import AccessSettings, get_access_settings
from app.modules.auth.providers import cloudflare_access
from app.modules.auth.providers.cloudflare_access import (
    AccessKeysUnavailableError,
    AccessSignInError,
    verify_access_jwt,
)

_TEAM = "wusool.cloudflareaccess.com"
_AUD = "aud-tag"
_KID = "test-key"


class _Keys:
    """Stands in for PyJWKClient and counts how often the keys are refetched."""

    def __init__(self, keys: list[jwt.PyJWK]) -> None:
        self.keys = keys
        self.refreshes = 0
        self.error: Exception | None = None

    def get_signing_keys(self, refresh: bool = False) -> list[jwt.PyJWK]:
        if self.error:
            raise self.error
        self.refreshes += refresh
        return self.keys


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def keys(monkeypatch: pytest.MonkeyPatch, private_key: rsa.RSAPrivateKey) -> _Keys:
    settings = AccessSettings(cf_access_team_domain=_TEAM, cf_access_engine_aud=_AUD)
    monkeypatch.setattr(cloudflare_access, "get_access_settings", lambda: settings)
    jwk = {**json.loads(RSAAlgorithm.to_jwk(private_key.public_key())), "kid": _KID}
    resolver = _Keys([jwt.PyJWK.from_dict(jwk)])
    monkeypatch.setattr(cloudflare_access, "_key_resolver", lambda _team: resolver)
    # Each test starts with the refresh allowance unspent.
    monkeypatch.setattr(cloudflare_access, "_last_refresh", None)
    return resolver


def _token(private_key: rsa.RSAPrivateKey, kid: str = _KID, **overrides: object) -> str:
    claims: dict[str, object] = {
        "email": "Jules@WusoolCapital.com",
        "sub": "user-1",
        "aud": [_AUD],
        "iss": f"https://{_TEAM}",
        "exp": int(time.time()) + 300,
    }
    claims.update(overrides)
    payload = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(payload, private_key, "RS256", headers={"kid": kid})


async def test_a_valid_token_yields_the_lowercased_email(private_key: rsa.RSAPrivateKey) -> None:
    claims = await verify_access_jwt(_token(private_key))

    assert (claims.email, claims.sub) == ("jules@wusoolcapital.com", "user-1")


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 10},
        {"aud": ["someone-else"]},
        {"iss": "https://evil.cloudflareaccess.com"},
        {"email": None},
        {"exp": None},
    ],
)
async def test_a_bad_token_is_refused(
    private_key: rsa.RSAPrivateKey, overrides: dict[str, object]
) -> None:
    with pytest.raises(AccessSignInError):
        await verify_access_jwt(_token(private_key, **overrides))


async def test_a_token_signed_by_another_key_is_refused() -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(AccessSignInError):
        await verify_access_jwt(_token(other))


async def test_garbage_is_refused() -> None:
    with pytest.raises(AccessSignInError):
        await verify_access_jwt("not-a-jwt")


async def test_an_unconfigured_api_refuses_everything(
    monkeypatch: pytest.MonkeyPatch, private_key: rsa.RSAPrivateKey
) -> None:
    monkeypatch.setattr(cloudflare_access, "get_access_settings", lambda: AccessSettings())

    with pytest.raises(AccessSignInError):
        await verify_access_jwt(_token(private_key))


def test_settings_default_to_off() -> None:
    get_access_settings.cache_clear()
    assert AccessSettings().cf_access_team_domain is None


async def test_an_unknown_key_id_refetches_the_keys_once_a_minute(
    private_key: rsa.RSAPrivateKey, keys: _Keys
) -> None:
    for _ in range(3):
        with pytest.raises(AccessSignInError, match="unknown key"):
            await verify_access_jwt(_token(private_key, kid="rotated-away"))

    assert keys.refreshes == 1


async def test_a_rotated_key_is_picked_up_by_the_one_allowed_refresh(
    monkeypatch: pytest.MonkeyPatch, private_key: rsa.RSAPrivateKey, keys: _Keys
) -> None:
    class _Rotating(_Keys):
        """Only a refetch brings in the new key."""

        def get_signing_keys(self, refresh: bool = False) -> list[jwt.PyJWK]:
            return self.keys if refresh else []

    rotating = _Rotating(keys.keys)
    monkeypatch.setattr(cloudflare_access, "_key_resolver", lambda _team: rotating)

    assert (await verify_access_jwt(_token(private_key))).sub == "user-1"


async def test_a_key_fetch_outage_is_not_reported_as_a_bad_token(
    private_key: rsa.RSAPrivateKey, keys: _Keys
) -> None:
    keys.error = jwt.PyJWKClientConnectionError("down")

    with pytest.raises(AccessKeysUnavailableError):
        await verify_access_jwt(_token(private_key))


async def test_the_first_refresh_is_allowed_on_a_freshly_booted_host(
    monkeypatch: pytest.MonkeyPatch, private_key: rsa.RSAPrivateKey, keys: _Keys
) -> None:
    """A monotonic clock under a minute must not count as a refresh a moment ago."""
    monkeypatch.setattr(cloudflare_access.time, "monotonic", lambda: 5.0)

    with pytest.raises(AccessSignInError):
        await verify_access_jwt(_token(private_key, kid="rotated-away"))

    assert keys.refreshes == 1
