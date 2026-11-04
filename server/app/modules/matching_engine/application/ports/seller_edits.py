"""Writing reviewed research to a seller. `ddl_commands` implements it with
its `/edit-seller` write (Attio first, then Postgres) and `server/main.py`
wires it, so this module never touches Attio or imports `ddl_commands`.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.modules.matching_engine.domain.matching.research import ResearchTarget, ResearchValue


@dataclass(frozen=True)
class SellerFieldEdit:
    name: str
    target: ResearchTarget
    value: ResearchValue


class SellerEditOutcome(StrEnum):
    SAVED = "saved"
    # A field was filled in since the research ran; nothing was written.
    CONFLICT = "conflict"
    INVALID = "invalid"
    # Some of the write reached Attio before a later step failed.
    PARTIAL = "partial"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class SellerEditResult:
    outcome: SellerEditOutcome
    conflicts: tuple[str, ...] = ()
    landed: tuple[str, ...] = ()
    message: str | None = None


class SellerEditPort(Protocol):
    async def apply(
        self, *, seller_role_id: str, edits: tuple[SellerFieldEdit, ...], requested_by: str
    ) -> SellerEditResult: ...
