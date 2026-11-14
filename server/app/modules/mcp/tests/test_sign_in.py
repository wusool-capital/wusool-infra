"""The sign-in flow over HTTP: Claude registers, the person signs in with Slack,
Claude swaps the code for tokens, and a refresh refuses someone who left."""

import base64
import hashlib
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from app.modules.auth import SlackIdentity
from app.modules.mcp.api import oauth
from app.modules.mcp.api.tokens import AccessClaims, TokenCodec
from app.modules.mcp.bootstrap import build_server
from app.modules.mcp.domain.signing import sign, unsign

_BASE = "https://tools.example"
_CLAUDE = "https://claude.ai/api/mcp/auth_callback"
_TEAM = "T_WUSOOL"
_MCP_HEADERS = {"accept": "application/json, text/event-stream"}


@dataclass
class Slack:
    member: AsyncMock
    identity: AsyncMock


@pytest.fixture
def slack(monkeypatch: pytest.MonkeyPatch) -> Slack:
    member = AsyncMock(return_value=True)
    identity = AsyncMock(return_value=SlackIdentity(user_id="U_ALICE", team_id=_TEAM, name="Alice"))
    monkeypatch.setattr(oauth, "is_active_member", member)
    monkeypatch.setattr(oauth, "identity_from_code", identity)
    monkeypatch.setattr(oauth, "workspace_team_id", AsyncMock(return_value=_TEAM))
    return Slack(member=member, identity=identity)


@pytest.fixture
def client() -> Iterator[TestClient]:
    server = build_server(
        public_url=_BASE,
        token_secret="secret",
        calls_per_hour=100,
        caller_source=lambda: pytest.fail("tools are not called here"),
    )
    with TestClient(
        server.streamable_http_app(stateless_http=True, json_response=True, host="tools.example"),
        base_url=_BASE,
        follow_redirects=False,
    ) as test_client:
        yield test_client


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/register",
        json={"redirect_uris": [_CLAUDE], "token_endpoint_auth_method": "client_secret_post"},
    )
    assert response.status_code == 201
    return response.json()


def _sign_in(client: TestClient, registered: dict[str, str]) -> tuple[str, str]:
    """Returns (code, verifier) after the Slack round trip."""
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    to_slack = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": registered["client_id"],
            "redirect_uri": _CLAUDE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "claude-state",
            "resource": f"{_BASE}/mcp",
        },
    )
    assert to_slack.status_code == 302
    slack_query = parse_qs(urlsplit(to_slack.headers["location"]).query)
    assert slack_query["redirect_uri"] == [f"{_BASE}/mcp/oauth/callback"]
    back = client.get(
        "/mcp/oauth/callback", params={"code": "slack-code", "state": slack_query["state"][0]}
    )
    assert back.status_code == 302
    location = urlsplit(back.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == _CLAUDE
    query = parse_qs(location.query)
    assert query["state"] == ["claude-state"]
    return query["code"][0], verifier


def _token(client: TestClient, registered: dict[str, str], **form: str) -> dict[str, str]:
    response = client.post(
        "/token",
        data={
            **form,
            "client_id": registered["client_id"],
            "client_secret": registered["client_secret"],
        },
    )
    return {"status": str(response.status_code), **response.json()}


def _exchange(
    client: TestClient, registered: dict[str, str], code: str, verifier: str
) -> dict[str, str]:
    return _token(
        client,
        registered,
        grant_type="authorization_code",
        code=code,
        code_verifier=verifier,
        redirect_uri=_CLAUDE,
        resource=f"{_BASE}/mcp",
    )


def test_registration_refuses_a_redirect_that_is_not_claude(client: TestClient) -> None:
    response = client.post(
        "/register",
        json={"redirect_uris": ["https://evil.example/cb"], "token_endpoint_auth_method": "none"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


def test_metadata_is_served(client: TestClient) -> None:
    metadata = client.get("/.well-known/oauth-authorization-server").json()
    resource = client.get("/.well-known/oauth-protected-resource/mcp").json()

    assert metadata["registration_endpoint"] == f"{_BASE}/register"
    assert "revocation_endpoint" not in metadata
    assert resource["resource"] == f"{_BASE}/mcp"


def test_full_sign_in_gives_a_token_that_opens_mcp(client: TestClient, slack: Slack) -> None:
    registered = _register(client)
    code, verifier = _sign_in(client, registered)

    tokens = _exchange(client, registered, code, verifier)

    assert tokens["status"] == "200", tokens
    assert tokens["scope"] == "crm"
    listed = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={**_MCP_HEADERS, "authorization": f"Bearer {tokens['access_token']}"},
    )
    assert listed.status_code == 200
    assert "add_buyer" in listed.text
    slack.member.assert_awaited_with("U_ALICE", allow_guests=False)


def test_a_code_works_only_once(client: TestClient, slack: Slack) -> None:
    registered = _register(client)
    code, verifier = _sign_in(client, registered)

    assert _exchange(client, registered, code, verifier)["status"] == "200"
    assert _exchange(client, registered, code, verifier)["status"] == "400"


def test_a_wrong_pkce_verifier_is_refused(client: TestClient, slack: Slack) -> None:
    registered = _register(client)
    code, _ = _sign_in(client, registered)

    assert _exchange(client, registered, code, "not-the-verifier" * 4)["status"] == "400"


def test_refresh_rechecks_membership_and_refuses_a_leaver(client: TestClient, slack: Slack) -> None:
    registered = _register(client)
    code, verifier = _sign_in(client, registered)
    refresh_token = _exchange(client, registered, code, verifier)["refresh_token"]

    refreshed = _token(client, registered, grant_type="refresh_token", refresh_token=refresh_token)
    assert refreshed["status"] == "200"

    slack.member.return_value = False
    refused = _token(client, registered, grant_type="refresh_token", refresh_token=refresh_token)
    assert refused["status"] == "400"
    assert refused["error"] == "invalid_grant"


def test_a_slack_outage_does_not_sign_people_out(client: TestClient, slack: Slack) -> None:
    registered = _register(client)
    code, verifier = _sign_in(client, registered)
    refresh_token = _exchange(client, registered, code, verifier)["refresh_token"]
    slack.member.return_value = None

    refreshed = _token(client, registered, grant_type="refresh_token", refresh_token=refresh_token)

    assert refreshed["status"] == "200"


@pytest.mark.parametrize(
    ("identity_team", "member"), [("T_OTHER", True), (_TEAM, False), (_TEAM, None)]
)
def test_sign_in_refuses_other_workspaces_guests_and_unconfirmed(
    client: TestClient, slack: Slack, identity_team: str, member: bool | None
) -> None:
    slack.identity.return_value = SlackIdentity(user_id="U_BOB", team_id=identity_team, name=None)
    slack.member.return_value = member
    registered = _register(client)
    to_slack = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": registered["client_id"],
            "redirect_uri": _CLAUDE,
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
            "state": "s",
        },
    )
    state = parse_qs(urlsplit(to_slack.headers["location"]).query)["state"][0]

    back = client.get("/mcp/oauth/callback", params={"code": "c", "state": state})

    query = parse_qs(urlsplit(back.headers["location"]).query)
    assert query["error"] == ["access_denied"]
    assert "code" not in query


def test_a_forged_state_never_redirects(client: TestClient) -> None:
    response = client.get("/mcp/oauth/callback", params={"code": "c", "state": "forged.state"})

    assert response.status_code == 400


def test_a_refresh_token_is_not_an_access_token(client: TestClient, slack: Slack) -> None:
    registered = _register(client)
    code, verifier = _sign_in(client, registered)
    refresh_token = _exchange(client, registered, code, verifier)["refresh_token"]

    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={**_MCP_HEADERS, "authorization": f"Bearer {refresh_token}"},
    )

    assert response.status_code == 401


def test_signing_rejects_tampering_and_other_purposes() -> None:
    token = sign(b"payload", purpose="access", key=b"k")

    assert unsign(token, purpose="access", key=b"k") == b"payload"
    assert unsign(token, purpose="refresh", key=b"k") is None
    assert unsign(token, purpose="access", key=b"other") is None
    assert unsign(token[:-2] + "xx", purpose="access", key=b"k") is None


def test_an_expired_token_does_not_decode() -> None:
    codec = TokenCodec(b"k")
    claims = AccessClaims(exp=100, client_fp="fp", scopes=("crm",), user_id="U", team_id="T")
    token = codec.encode("access", claims)

    assert codec.decode("access", token, AccessClaims, now=99) == claims
    assert codec.decode("access", token, AccessClaims, now=100) is None


def test_a_slack_outage_at_sign_in_refuses_cleanly(client: TestClient, slack: Slack) -> None:
    slack.identity.side_effect = ConnectionError("slack down")
    registered = _register(client)
    to_slack = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": registered["client_id"],
            "redirect_uri": _CLAUDE,
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
        },
    )
    state = parse_qs(urlsplit(to_slack.headers["location"]).query)["state"][0]

    back = client.get("/mcp/oauth/callback", params={"code": "c", "state": state})

    assert back.status_code == 302
    assert parse_qs(urlsplit(back.headers["location"]).query)["error"] == ["access_denied"]
