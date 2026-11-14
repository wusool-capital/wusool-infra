"""Seams phase 0 replaces with Postgres-backed adapters (roles, idempotency),
without any tool changing."""

from typing import Protocol

from app.modules.mcp.domain.access import Caller, Permission


class PermissionChecker(Protocol):
    def allows(self, caller: Caller, permission: Permission) -> bool: ...


class IdempotencyStore(Protocol):
    """A tool's serialized result per request key, so a retry replays it."""

    def get(self, key: str) -> str | None: ...

    def put(self, key: str, result: str) -> None: ...
