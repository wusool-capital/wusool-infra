"""What each signed OAuth artifact carries. Nothing is stored server-side: a
client id, code or token is its own record, verified by its signature and expiry."""

import hashlib
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from app.modules.mcp.domain.signing import sign, unsign

Purpose = Literal["client", "state", "code", "access", "refresh"]
AuthMethod = Literal["none", "client_secret_post", "client_secret_basic"]

CODE_SECONDS = 60
STATE_SECONDS = 600
ACCESS_SECONDS = 3600
REFRESH_SECONDS = 30 * 86400


class Claims(BaseModel):
    model_config = ConfigDict(frozen=True)

    exp: int | None = None


class ClientClaims(Claims):
    redirect_uris: tuple[str, ...]
    auth_method: AuthMethod
    client_name: str | None = None
    issued_at: int


class _Grant(Claims):
    # A hash, not the client id itself: a client id is long, and this keeps tokens short.
    client_fp: str
    scopes: tuple[str, ...]
    resource: str | None = None


class StateClaims(_Grant):
    redirect_uri: str
    redirect_uri_provided_explicitly: bool
    code_challenge: str
    client_state: str | None = None


class CodeClaims(StateClaims):
    jti: str
    user_id: str
    team_id: str
    name: str | None = None


class AccessClaims(_Grant):
    user_id: str
    team_id: str
    name: str | None = None


class RefreshClaims(AccessClaims):
    jti: str


C = TypeVar("C", bound=Claims)


def client_fingerprint(client_id: str) -> str:
    return hashlib.sha256(client_id.encode()).hexdigest()[:32]


class TokenCodec:
    def __init__(self, key: bytes) -> None:
        self._key = key

    @property
    def key(self) -> bytes:
        return self._key

    def encode(self, purpose: Purpose, claims: Claims) -> str:
        return sign(claims.model_dump_json().encode(), purpose=purpose, key=self._key)

    def decode(self, purpose: Purpose, token: str, model: type[C], *, now: float) -> C | None:
        """None for anything tampered with, malformed, expired or of another purpose."""
        payload = unsign(token, purpose=purpose, key=self._key)
        if payload is None:
            return None
        try:
            claims = model.model_validate_json(payload)
        except ValidationError:
            return None
        if claims.exp is not None and claims.exp <= now:
            return None
        return claims
