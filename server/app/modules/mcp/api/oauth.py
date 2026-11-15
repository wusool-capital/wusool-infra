"""The MCP's OAuth 2.1 authorization server, per the MCP authorization spec.
Claude registers itself, the person signs in with Slack, and Claude gets a
1-hour access token plus a 30-day refresh token.

Stateless: client ids, codes and tokens are HMAC-signed records (see `tokens.py`),
so a deploy signs nobody out and there is nothing to store. The cost: a refresh
token can't be revoked one by one. The controls are the 1-hour access token, the
Slack membership check on every refresh, and rotating `MCP_TOKEN_SECRET`.
"""

import logging
import secrets
import time
from collections.abc import Callable
from urllib.parse import urlsplit

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    IdentityAssertionParams,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response

from app.modules.auth import (
    SlackSignInError,
    authorize_url,
    identity_from_code,
    is_active_member,
    workspace_team_id,
)
from app.modules.mcp.api.tokens import (
    ACCESS_SECONDS,
    CODE_SECONDS,
    REFRESH_SECONDS,
    STATE_SECONDS,
    AccessClaims,
    AuthMethod,
    ClientClaims,
    CodeClaims,
    RefreshClaims,
    StateClaims,
    TokenCodec,
    client_fingerprint,
)
from app.modules.mcp.application.ports.stores import IdempotencyStore
from app.modules.mcp.domain.access import CRM_SCOPE
from app.modules.mcp.domain.signing import derive

logger = logging.getLogger(__name__)

CALLBACK_PATH = "/mcp/oauth/callback"
_CLIENT_ID_PREFIX = "wc1."
# Only Claude's connector callback and local tools (MCP Inspector) may receive a code.
_ALLOWED_REDIRECTS = frozenset(
    {"https://claude.ai/api/mcp/auth_callback", "https://claude.com/api/mcp/auth_callback"}
)
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1"})


class SlackAuthorizationCode(AuthorizationCode):
    team_id: str
    name: str | None = None
    jti: str


class SlackRefreshToken(RefreshToken):
    team_id: str
    name: str | None = None


def redirect_allowed(uri: str) -> bool:
    if uri in _ALLOWED_REDIRECTS:
        return True
    parts = urlsplit(uri)
    return parts.scheme == "http" and parts.hostname in _LOOPBACK_HOSTS


class WusoolOAuthProvider:
    def __init__(
        self,
        *,
        public_url: str,
        codec: TokenCodec,
        used_codes: IdempotencyStore,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._public_url = public_url.rstrip("/")
        self._codec = codec
        self._used_codes = used_codes
        self._clock = clock

    @property
    def resource(self) -> str:
        return f"{self._public_url}/mcp"

    # Client registration -------------------------------------------------------

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Replaces the SDK's random id with a signed record of the client, and
        derives its secret from that id, so `get_client` needs no storage."""
        uris = tuple(str(u) for u in client_info.redirect_uris or ())
        refused = [u for u in uris if not redirect_allowed(u)]
        if not uris or refused:
            raise RegistrationError(
                "invalid_redirect_uri", "only Claude's connector callback or localhost may sign in"
            )
        method = client_info.token_endpoint_auth_method
        if method not in ("none", "client_secret_post", "client_secret_basic"):
            raise RegistrationError("invalid_client_metadata", "unsupported auth method")
        auth_method: AuthMethod = method
        claims = ClientClaims(
            redirect_uris=uris,
            auth_method=auth_method,
            client_name=client_info.client_name,
            issued_at=int(self._clock()),
        )
        client_id = _CLIENT_ID_PREFIX + self._codec.encode("client", claims)
        client_info.client_id = client_id
        client_info.client_secret = self._client_secret(client_id, auth_method)
        client_info.client_secret_expires_at = 0 if client_info.client_secret else None
        client_info.scope = CRM_SCOPE

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        if not client_id.startswith(_CLIENT_ID_PREFIX):
            return None
        claims = self._codec.decode(
            "client", client_id.removeprefix(_CLIENT_ID_PREFIX), ClientClaims, now=self._clock()
        )
        if claims is None:
            return None
        return OAuthClientInformationFull(
            client_id=client_id,
            client_secret=self._client_secret(client_id, claims.auth_method),
            client_secret_expires_at=0,
            client_id_issued_at=claims.issued_at,
            redirect_uris=[AnyUrl(u) for u in claims.redirect_uris],
            token_endpoint_auth_method=claims.auth_method,
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope=CRM_SCOPE,
            client_name=claims.client_name,
        )

    def _client_secret(self, client_id: str, method: AuthMethod) -> str | None:
        if method == "none":
            return None
        return derive(client_id, purpose="client-secret", key=self._codec.key)

    # Authorization: Claude -> Slack -> callback -> Claude ----------------------

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        if params.resource is not None and params.resource.rstrip("/") != self.resource:
            raise AuthorizeError("invalid_target", "this server only issues tokens for /mcp")
        scopes = tuple(params.scopes or [CRM_SCOPE])
        if set(scopes) - {CRM_SCOPE}:
            raise AuthorizeError("invalid_scope", f"only the '{CRM_SCOPE}' scope exists")
        state = StateClaims(
            exp=int(self._clock()) + STATE_SECONDS,
            client_fp=client_fingerprint(client.client_id),
            scopes=scopes,
            resource=self.resource,
            redirect_uri=str(params.redirect_uri),
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            code_challenge=params.code_challenge,
            client_state=params.state,
        )
        try:
            team_id: str | None = await workspace_team_id()
        except Exception:
            logger.warning("mcp_slack_workspace_lookup_failed")
            team_id = None
        return authorize_url(
            state=self._codec.encode("state", state),
            team_id=team_id,
            redirect_uri=self._public_url + CALLBACK_PATH,
        )

    async def slack_callback(self, request: Request) -> Response:
        """Slack sends the person back here. Only after the signed state checks out
        is its redirect URI trusted, for success and refusal alike."""
        params = request.query_params
        state = self._codec.decode(
            "state", params.get("state") or "", StateClaims, now=self._clock()
        )
        if state is None:
            return PlainTextResponse(
                "This sign-in link has expired. Start again from Claude.", status_code=400
            )
        if params.get("error") or not params.get("code"):
            return self._refuse(state, "Slack sign-in was cancelled")
        try:
            identity = await identity_from_code(
                params["code"], redirect_uri=self._public_url + CALLBACK_PATH
            )
            allowed_team = await workspace_team_id()
        except SlackSignInError as exc:
            logger.warning("mcp_sign_in_failed reason=%s", exc)
            return self._refuse(state, "Slack sign-in failed")
        except Exception:
            # Slack's API or the network failed: Claude still gets a clear refusal, not a 500.
            logger.exception("mcp_sign_in_slack_unreachable")
            return self._refuse(state, "Couldn't reach Slack. Try again in a minute")
        if identity.team_id != allowed_team:
            return self._refuse(state, "Sign in with the Wusool Slack workspace")
        # Unlike a refresh, a first sign-in is refused when Slack can't confirm membership.
        if await is_active_member(identity.user_id, allow_guests=False) is not True:
            logger.info("mcp_sign_in_refused user=%s", identity.user_id)
            return self._refuse(state, "Only active Wusool team members can connect")

        code = CodeClaims(
            **state.model_dump(exclude={"exp"}),
            exp=int(self._clock()) + CODE_SECONDS,
            jti=secrets.token_urlsafe(16),
            user_id=identity.user_id,
            team_id=identity.team_id,
            name=identity.name,
        )
        logger.info("mcp_sign_in user=%s", identity.user_id)
        return RedirectResponse(
            construct_redirect_uri(
                state.redirect_uri,
                code=self._codec.encode("code", code),
                state=state.client_state,
                iss=self._public_url,
            ),
            status_code=302,
        )

    def _refuse(self, state: StateClaims, reason: str) -> Response:
        return RedirectResponse(
            construct_redirect_uri(
                state.redirect_uri,
                error="access_denied",
                error_description=reason,
                state=state.client_state,
            ),
            status_code=302,
        )

    # Tokens --------------------------------------------------------------------

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> SlackAuthorizationCode | None:
        claims = self._codec.decode("code", authorization_code, CodeClaims, now=self._clock())
        if claims is None or claims.client_fp != client_fingerprint(client.client_id):
            return None
        if claims.exp is None or self._used_codes.get(claims.jti) is not None:
            return None
        return SlackAuthorizationCode(
            code=authorization_code,
            scopes=list(claims.scopes),
            expires_at=claims.exp,
            client_id=client.client_id,
            code_challenge=claims.code_challenge,
            redirect_uri=AnyUrl(claims.redirect_uri),
            redirect_uri_provided_explicitly=claims.redirect_uri_provided_explicitly,
            resource=claims.resource,
            subject=claims.user_id,
            team_id=claims.team_id,
            name=claims.name,
            jti=claims.jti,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: SlackAuthorizationCode
    ) -> OAuthToken:
        if self._used_codes.get(authorization_code.jti) is not None:
            raise TokenError("invalid_grant", "authorization code already used")
        self._used_codes.put(authorization_code.jti, "used")
        assert authorization_code.subject is not None  # every code we sign names its person
        return self._issue(
            client,
            user_id=authorization_code.subject,
            team_id=authorization_code.team_id,
            name=authorization_code.name,
            scopes=tuple(authorization_code.scopes),
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> SlackRefreshToken | None:
        claims = self._codec.decode("refresh", refresh_token, RefreshClaims, now=self._clock())
        if claims is None or claims.client_fp != client_fingerprint(client.client_id):
            return None
        return SlackRefreshToken(
            token=refresh_token,
            client_id=client.client_id,
            scopes=list(claims.scopes),
            expires_at=claims.exp,
            resource=claims.resource,
            subject=claims.user_id,
            team_id=claims.team_id,
            name=claims.name,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: SlackRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        assert refresh_token.subject is not None  # every refresh token we sign names its person
        active = await is_active_member(refresh_token.subject, allow_guests=False)
        if active is False:
            logger.info("mcp_refresh_refused user=%s", refresh_token.subject)
            raise TokenError("invalid_grant", "no longer an active Wusool team member")
        if active is None:
            # An outage must not sign everyone out; the next refresh checks again.
            logger.warning("mcp_refresh_member_check_skipped user=%s", refresh_token.subject)
        return self._issue(
            client,
            user_id=refresh_token.subject,
            team_id=refresh_token.team_id,
            name=refresh_token.name,
            scopes=tuple(scopes or refresh_token.scopes),
        )

    def _issue(
        self,
        client: OAuthClientInformationFull,
        *,
        user_id: str,
        team_id: str,
        name: str | None,
        scopes: tuple[str, ...],
    ) -> OAuthToken:
        now = int(self._clock())
        access = AccessClaims(
            exp=now + ACCESS_SECONDS,
            client_fp=client_fingerprint(client.client_id),
            scopes=scopes,
            resource=self.resource,
            user_id=user_id,
            team_id=team_id,
            name=name,
        )
        refresh = RefreshClaims(
            **access.model_dump(exclude={"exp"}),
            exp=now + REFRESH_SECONDS,
            jti=secrets.token_urlsafe(16),
        )
        return OAuthToken(
            access_token=self._codec.encode("access", access),
            expires_in=ACCESS_SECONDS,
            scope=" ".join(scopes),
            refresh_token=self._codec.encode("refresh", refresh),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        claims = self._codec.decode("access", token, AccessClaims, now=self._clock())
        if claims is None:
            return None
        return AccessToken(
            token=token,
            client_id=claims.client_fp,
            scopes=list(claims.scopes),
            expires_at=claims.exp,
            resource=claims.resource,
            subject=claims.user_id,
            claims={"team_id": claims.team_id, "name": claims.name, "iss": self._public_url},
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        """Revocation is not advertised: a signed token has nothing to delete."""

    async def exchange_identity_assertion(
        self, client: OAuthClientInformationFull, params: IdentityAssertionParams
    ) -> OAuthToken:
        """Not advertised (`identity_assertion_enabled` stays off)."""
        raise TokenError("unsupported_grant_type", "identity assertions are not supported")
