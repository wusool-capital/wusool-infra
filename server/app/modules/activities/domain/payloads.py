"""Typed `activities.payload` models, one per event shape.

A payload holds only the event's own facts. Detail that lives in a domain
ledger (answers, scores, transcripts) is reached through the row's ledger FK,
never copied here. Field names, not values, for anything that can hold PII.

Each model carries a `kind` discriminator so the persistence layer can
validate and serialize the union without `dict` or `Any` crossing the boundary.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class NoPayload:
    """Event fully described by its type, subject and ledger link."""

    kind: Literal["none"] = "none"


@dataclass(frozen=True, kw_only=True)
class CrmRecordPayload:
    kind: Literal["crm_record"] = "crm_record"
    attio_event_type: str
    attio_object: str | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileWritePayload:
    kind: Literal["profile_write"] = "profile_write"
    changed_fields: tuple[str, ...] = ()
    is_new_org: bool = False


@dataclass(frozen=True, kw_only=True)
class MatchRunPayload:
    kind: Literal["match_run"] = "match_run"
    candidate_count: int = 0


@dataclass(frozen=True, kw_only=True)
class MatchDecisionPayload:
    kind: Literal["match_decision"] = "match_decision"
    deal_attio_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class MeetingPayload:
    kind: Literal["meeting"] = "meeting"
    pushed_to_attio: bool = False


@dataclass(frozen=True, kw_only=True)
class StageChangePayload:
    kind: Literal["stage_change"] = "stage_change"
    from_stage: str | None = None
    to_stage: str


ActivityPayload = (
    NoPayload
    | CrmRecordPayload
    | ProfileWritePayload
    | MatchRunPayload
    | MatchDecisionPayload
    | MeetingPayload
    | StageChangePayload
)
