"""Shared addresses and domains left for a person to sort out, and the post about them."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.modules.interactions.domain.linking import Ambiguity


@dataclass(frozen=True)
class ReviewCase:
    kind: Ambiguity
    # The shared address or domain.
    value: str
    # The Persons or Organizations it matches.
    record_ids: tuple[str, ...]


@dataclass(frozen=True)
class OpenReview:
    kind: Ambiguity
    value: str
    # Subject of the latest interaction involving the value, for context.
    subject: str | None
    record_count: int
    # Whether the digest has already listed it.
    notified: bool = False


class ReviewStorePort(Protocol):
    async def sync_open(self, cases: Sequence[ReviewCase]) -> None:
        """Opens cases not seen before and resolves open items that are no longer in `cases`.
        A case a person dismissed stays dismissed."""
        ...

    async def list_open(self) -> tuple[OpenReview, ...]: ...

    async def mark_notified(self, items: Sequence[OpenReview]) -> None: ...


class DigestPosterPort(Protocol):
    async def post(self, text: str) -> None: ...
