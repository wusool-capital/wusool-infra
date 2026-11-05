from urllib.parse import parse_qs

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import jwt

from app.modules.google_workspace.providers.google.auth import (
    DelegatedTokenSource,
    GoogleAuthError,
    ServiceAccountKey,
)
from app.modules.google_workspace.tests.fakes.google import http_client

JULES = "jules@wusoolcapital.com"
RAMZY = "ramzy@wusoolcapital.com"
SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
)


def _key() -> ServiceAccountKey:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return ServiceAccountKey(
        client_email="reader@proj.iam.gserviceaccount.com", private_key=pem, private_key_id="kid-1"
    )


class _Clock:
    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


class _TokenEndpoint:
    def __init__(self, response: httpx.Response | None = None) -> None:
        self.forms: list[dict[str, list[str]]] = []
        self._response = response

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.forms.append(parse_qs(request.content.decode()))
        return self._response or httpx.Response(
            200, json={"access_token": f"tok-{len(self.forms)}", "expires_in": 3600}
        )


async def test_the_signed_assertion_names_the_mailbox_and_both_scopes() -> None:
    endpoint = _TokenEndpoint()
    clock = _Clock()
    async with http_client(endpoint) as http:
        source = DelegatedTokenSource(_key(), http, SCOPES, clock)
        token = await source.token(JULES)

    form = endpoint.forms[0]
    assert token == "tok-1"
    assert form["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]
    claims = jwt.decode(form["assertion"][0], verify=False)
    assert claims["iss"] == "reader@proj.iam.gserviceaccount.com"
    assert claims["sub"] == JULES
    assert claims["scope"] == " ".join(SCOPES)
    assert claims["aud"] == "https://oauth2.googleapis.com/token"
    assert claims["iat"] == int(clock.now)
    assert claims["exp"] - claims["iat"] == 3600
    assert jwt.decode_header(form["assertion"][0])["kid"] == "kid-1"


async def test_a_token_is_reused_until_just_before_it_expires() -> None:
    endpoint = _TokenEndpoint()
    clock = _Clock()
    async with http_client(endpoint) as http:
        source = DelegatedTokenSource(_key(), http, SCOPES, clock)
        first = await source.token(JULES)
        clock.now += 3500
        reused = await source.token(JULES)
        clock.now += 100
        refreshed = await source.token(JULES)

    assert (first, reused, refreshed) == ("tok-1", "tok-1", "tok-2")
    assert len(endpoint.forms) == 2


async def test_each_mailbox_gets_its_own_token() -> None:
    endpoint = _TokenEndpoint()
    async with http_client(endpoint) as http:
        source = DelegatedTokenSource(_key(), http, SCOPES, _Clock())
        await source.token(JULES)
        await source.token(RAMZY)

    claims = [jwt.decode(f["assertion"][0], verify=False)["sub"] for f in endpoint.forms]
    assert claims == [JULES, RAMZY]


async def test_a_refusal_names_the_mailbox_and_googles_reason() -> None:
    refusal = httpx.Response(
        400, json={"error": "unauthorized_client", "error_description": "not authorized"}
    )
    async with http_client(_TokenEndpoint(refusal)) as http:
        source = DelegatedTokenSource(_key(), http, SCOPES, _Clock())
        with pytest.raises(GoogleAuthError) as caught:
            await source.token(JULES)

    assert str(caught.value) == (
        f"Google refused a token for {JULES}: unauthorized_client: not authorized"
    )


async def test_a_refusal_that_is_not_json_still_raises_a_clear_error() -> None:
    async with http_client(
        _TokenEndpoint(httpx.Response(502, text="<html>bad gateway</html>"))
    ) as http:
        source = DelegatedTokenSource(_key(), http, SCOPES, _Clock())
        with pytest.raises(GoogleAuthError) as caught:
            await source.token(JULES)

    assert str(caught.value) == f"Google refused a token for {JULES}: HTTP 502"


def test_the_key_parses_from_the_downloaded_json_and_ignores_extra_fields() -> None:
    key = ServiceAccountKey.model_validate_json(
        '{"type": "service_account", "client_email": "a@b.iam.gserviceaccount.com",'
        ' "private_key": "pem", "private_key_id": "k", "client_id": "123"}'
    )

    assert key.client_email == "a@b.iam.gserviceaccount.com"
    assert key.token_uri == "https://oauth2.googleapis.com/token"
