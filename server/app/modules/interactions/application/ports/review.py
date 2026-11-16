"""Shared addresses and domains left for a person to sort out, and the daily post about them."""

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


class ReviewStorePort(Protocol):
    async def save_open(self, cases: Sequence[ReviewCase]) -> None:
        """One open item per kind and value; a case that is already open is left as it is."""
        ...

    async def list_open(self) -> tuple[OpenReview, ...]: ...


class DigestPosterPort(Protocol):
    async def post(self, text: str) -> None: ...
