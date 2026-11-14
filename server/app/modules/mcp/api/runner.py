"""The one path every tool call takes: who is calling, may they, have they sent
this request before, are they over their limit. Then one log line, and errors
turned into plain sentences for Claude (never a stack trace)."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar
from weakref import WeakValueDictionary

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from app.modules.ddl_commands import (
    BuyerNotFoundError,
    InvalidFieldsError,
    InvalidUploadError,
    OrgMismatchError,
    OrgRemovedError,
    PartialWriteError,
    PreviewNotFoundError,
    RowProblem,
    SellerNotFoundError,
)
from app.modules.mcp.application.ports import IdempotencyStore, PermissionChecker
from app.modules.mcp.domain.access import Caller, Permission
from app.modules.utilities import FixedWindowRateLimiter
from app.modules.utilities.domain.safe_errors import describe_error

logger = logging.getLogger(__name__)

ResultT = TypeVar("ResultT", bound=BaseModel)
CallerSource = Callable[[], Caller]
_MAX_PROBLEMS_SHOWN = 50


def caller_from_token() -> Caller:
    token = get_access_token()
    if token is None or token.subject is None:
        raise ToolError("Sign in to Wusool first.")
    claims = token.claims or {}
    name = claims.get("name")
    return Caller(
        slack_user_id=token.subject,
        team_id=str(claims.get("team_id", "")),
        name=name if isinstance(name, str) else None,
        scopes=tuple(token.scopes),
    )


def describe_problems(problems: tuple[RowProblem, ...]) -> str:
    shown = [f"row {p.row}: {p.message}" for p in problems[:_MAX_PROBLEMS_SHOWN]]
    more = len(problems) - len(shown)
    return "\n".join(shown + ([f"…and {more} more"] if more > 0 else []))


def _message(exc: Exception) -> str | None:
    """The sentence Claude sees for an error we expect, or None for a crash."""
    match exc:
        case InvalidFieldsError():
            problems = describe_problems(exc.problems)
            return f"Nothing was saved. Fix these fields and try again:\n{problems}"
        case InvalidUploadError():
            return f"Nothing was saved: {exc}"
        case PreviewNotFoundError():
            return "That import preview has expired or doesn't exist. Send the list again."
        case BuyerNotFoundError():
            return "No buyer has that id. Use find_buyers to get it."
        case SellerNotFoundError():
            return "No seller has that id. Use find_sellers to get it."
        case OrgRemovedError():
            return "That company was deleted in Attio, so it can't be edited."
        case OrgMismatchError():
            return "That record no longer belongs to the same company. Look it up again."
        case PartialWriteError():
            cause = describe_error(exc.cause)
            if not exc.landed:
                return f"Couldn't save to Attio, so nothing was saved ({cause})."
            return f"Saved only partway ({cause}). Already saved: {'; '.join(exc.landed)}."
    return None


class ToolRunner:
    def __init__(
        self,
        *,
        permissions: PermissionChecker,
        results: IdempotencyStore,
        limiter: FixedWindowRateLimiter,
        caller_source: CallerSource = caller_from_token,
    ) -> None:
        self._permissions = permissions
        self._results = results
        self._limiter = limiter
        self._caller_source = caller_source
        self._locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()

    async def run(
        self,
        tool: str,
        permission: Permission,
        call: Callable[[Caller], Awaitable[ResultT]],
        *,
        output: type[ResultT],
        request_id: str | None = None,
    ) -> ResultT:
        started = time.monotonic()
        caller = self._caller_source()
        result_code = "ok"
        try:
            if not self._permissions.allows(caller, permission):
                result_code = "forbidden"
                raise ToolError(f"You don't have access to {tool}.")
            if not self._limiter.check(caller.slack_user_id):
                result_code = "rate_limited"
                raise ToolError("Too many Wusool requests this hour. Try again later.")
            if request_id is None:
                return await call(caller)
            key = f"{caller.slack_user_id}:{tool}:{request_id}"
            # Held across the call, so a retry sent while the first is running waits for it.
            async with self._locks.setdefault(key, asyncio.Lock()):
                stored = self._results.get(key)
                if stored is not None:
                    result_code = "replayed"
                    return output.model_validate_json(stored)
                result = await call(caller)
                self._results.put(key, result.model_dump_json())
                return result
        except ToolError:
            if result_code == "ok":
                result_code = "refused"
            raise
        except Exception as exc:
            message = _message(exc)
            if message is None:
                result_code = "error"
                raise
            result_code = type(exc).__name__
            raise ToolError(message) from exc
        finally:
            logger.info(
                "mcp_tool_call tool=%s user=%s duration_ms=%d result=%s",
                tool,
                caller.slack_user_id,
                (time.monotonic() - started) * 1000,
                result_code,
            )
