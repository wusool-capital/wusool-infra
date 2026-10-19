"""The value objects a writer hands to `ActivityRecorderPort`."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.activities.domain.payloads import ActivityPayload, NoPayload
from app.modules.activities.domain.vocabulary import (
    ActivitySource,
    ActorType,
    EventType,
    SubjectType,
)

_LEDGER_LINKS = (
    "tool_run_id",
    "match_result_id",
    "meeting_id",
    "command_run_id",
    "deal_stage_event_id",
    "signal_id",
)


@dataclass(frozen=True)
class ActivityActor:
    type: ActorType
    # Raw actor id: Slack user, Attio member/token, Scribe install, process name.
    ref: str | None = None
    # Set only for an Attio workspace member; the recorder drops it when the
    # member is not in `users`, so the FK can never fail a write.
    attio_member_id: str | None = None

    @classmethod
    def slack(cls, user_id: str | None) -> "ActivityActor":
        if not user_id:
            return cls(ActorType.UNKNOWN)
        return cls(ActorType.SLACK_USER, user_id)

    @classmethod
    def system(cls, name: str) -> "ActivityActor":
        return cls(ActorType.SYSTEM, name)

    @classmethod
    def scribe(cls, install_id: str | None) -> "ActivityActor":
        return cls(ActorType.SCRIBE_INSTALL, install_id)

    @classmethod
    def visitor(cls) -> "ActivityActor":
        return cls(ActorType.WEBSITE_VISITOR)

    @classmethod
    def attio(cls, actor_type: str | None, actor_id: str | None) -> "ActivityActor":
        """Maps Attio's webhook actor (`workspace-member`, `api-token`, `system`)."""
        match actor_type:
            case "workspace-member":
                return cls(ActorType.ATTIO_MEMBER, actor_id, actor_id)
            case "api-token":
                return cls(ActorType.ATTIO_API_TOKEN, actor_id)
            case "system":
                return cls(ActorType.ATTIO_SYSTEM, actor_id)
            case _:
                return cls(ActorType.UNKNOWN, actor_id)


@dataclass(frozen=True)
class ActivityEvent:
    subject_type: SubjectType
    event_type: EventType
    source: ActivitySource
    actor: ActivityActor
    payload: ActivityPayload = NoPayload()
    subject_attio_id: str | None = None
    subject_uuid: UUID | None = None
    outcome: str | None = None
    # Event time. None means "now"; set it when the event happened earlier.
    occurred_at: datetime | None = None
    idempotency_key: str | None = None
    # Typed links to the ledger row holding the detail; at most one.
    tool_run_id: UUID | None = None
    match_result_id: UUID | None = None
    meeting_id: UUID | None = None
    command_run_id: UUID | None = None
    deal_stage_event_id: UUID | None = None
    signal_id: UUID | None = None

    def __post_init__(self) -> None:
        # Mirrors `activities_subject_present` and `activities_single_ledger_link`
        # so a bad event fails in the writer, not in the database.
        if self.subject_attio_id is None and self.subject_uuid is None:
            raise ValueError("an activity needs subject_attio_id or subject_uuid")
        linked = [name for name in _LEDGER_LINKS if getattr(self, name) is not None]
        if len(linked) > 1:
            raise ValueError(f"an activity links at most one ledger row, got {linked}")
