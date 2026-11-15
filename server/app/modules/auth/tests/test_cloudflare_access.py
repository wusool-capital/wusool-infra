import json
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.modules.auth.config import AccessSettings, get_access_settings
from app.modules.auth.providers import cloudflare_access
from app.modules.auth.providers.cloudflare_access import AccessSignInError, verify_access_jwt

_TEAM = "wusool.cloudflareaccess.com"
_AUD = "aud-tag"


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def configured(monkeypatch: pytest.MonkeyPatch, private_key: rsa.RSAPrivateKey) -> None:
    settings = AccessSettings(cf_access_team_domain=_TEAM, cf_access_engine_aud=_AUD)
    monkeypatch.setattr(cloudflare_access, "get_access_settings", lambda: settings)
    signing_key = jwt.PyJWK.from_dict(json.loads(RSAAlgorithm.to_jwk(private_key.public_key())))
    resolver = SimpleNamespace(get_signing_key_from_jwt=lambda _token: signing_key)
    monkeypatch.setattr(cloudflare_access, "_key_resolver", lambda _team: resolver)


def _token(private_key: rsa.RSAPrivateKey, **overrides: object) -> str:
    claims: dict[str, object] = {
        "email": "Jules@WusoolCapital.com",
        "sub": "user-1",
        "aud": [_AUD],
        "iss": f"https://{_TEAM}",
        "exp": int(time.time()) + 300,
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, private_key, "RS256")


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
