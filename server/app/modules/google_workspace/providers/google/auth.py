"""Domain-wide delegation: a service account acting as one mailbox.

The server signs a short-lived JWT naming the mailbox in `sub` and trades it
at Google's token endpoint. Only `google-auth`'s signer is used; the call
itself goes through `httpx`, so nothing here needs a sync HTTP transport.
"""

import asyncio
import time
from collections.abc import Callable

import httpx
from google.auth import jwt
from google.auth.crypt import RSASigner
from pydantic import BaseModel, ConfigDict

_TOKEN_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"
_JWT_LIFETIME_S = 3600
_REFRESH_MARGIN_S = 60


class GoogleAuthError(Exception):
    """Google refused to issue a token for a mailbox."""


class ServiceAccountKey(BaseModel):
    """The fields we need from the downloaded service-account JSON key."""

    model_config = ConfigDict(frozen=True, extra="ignore", hide_input_in_errors=True)

    client_email: str
    private_key: str
    private_key_id: str
    token_uri: str = "https://oauth2.googleapis.com/token"


class _TokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str
    expires_in: int


class _TokenError(BaseModel):
    model_config = ConfigDict(extra="ignore")

    error: str
    error_description: str | None = None


class DelegatedTokenSource:
    def __init__(
        self,
        key: ServiceAccountKey,
        http: httpx.AsyncClient,
        scopes: tuple[str, ...],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._key = key
        self._http = http
        self._scopes = " ".join(scopes)
        self._clock = clock
        self._signer = RSASigner.from_string(key.private_key, key.private_key_id)
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def token(self, mailbox: str) -> str:
        async with self._lock:
            cached = self._cache.get(mailbox)
            if cached and cached[1] - _REFRESH_MARGIN_S > self._clock():
                return cached[0]
            issued = await self._exchange(mailbox)
            self._cache[mailbox] = (issued.access_token, self._clock() + issued.expires_in)
            return issued.access_token

    async def _exchange(self, mailbox: str) -> _TokenResponse:
        now = int(self._clock())
        claims: dict[str, str | int] = {
            "iss": self._key.client_email,
            "sub": mailbox,
            "scope": self._scopes,
            "aud": self._key.token_uri,
            "iat": now,
            "exp": now + _JWT_LIFETIME_S,
        }
        assertion = jwt.encode(self._signer, claims, key_id=self._key.private_key_id).decode()
        response = await self._http.post(
            self._key.token_uri, data={"grant_type": _TOKEN_GRANT, "assertion": assertion}
        )
        if response.status_code != 200:
            raise GoogleAuthError(_refusal(mailbox, response))
        return _TokenResponse.model_validate_json(response.content)


def _refusal(mailbox: str, response: httpx.Response) -> str:
    try:
        error = _TokenError.model_validate_json(response.content)
    except ValueError:
        return f"Google refused a token for {mailbox}: HTTP {response.status_code}"
    detail = f": {error.error_description}" if error.error_description else ""
    return f"Google refused a token for {mailbox}: {error.error}{detail}"
