"""The business-event index (`activities`) — one thin, append-only row per
meaningful event: who (actor) did what (`event_type`) to which record
(subject), when (`ts`), with what result (`outcome`), plus a typed FK to the
domain ledger (`tool_runs`, `match_results`, `meetings`, `command_runs`,
`deal_stage_events`, `signals`) that holds the detail. See
`docs/internal/dev/ACTIVITIES_AUDIT.md`.

A peer module, not a full-access one: consumers import this root's `__all__`
(the vocabulary, payloads, `ActivityEvent`, `ActivityRecorderPort` and the
concrete `SqlAlchemyActivityRecorder` and `SqlAlchemyDealStageRecorder` their
persistence layers construct). It
imports no other business module, so the module graph stays acyclic.
"""

from app.modules.activities.application.ports.recorder import ActivityRecorderPort
from app.modules.activities.domain.event import ActivityActor, ActivityEvent, LedgerRef
from app.modules.activities.domain.payloads import (
    ActivityPayload,
    CrmRecordPayload,
    LinkedInScanPayload,
    MatchDecisionPayload,
    MatchRunPayload,
    MeetingPayload,
    NoPayload,
    ProfileWritePayload,
    StageChangePayload,
)
from app.modules.activities.domain.vocabulary import (
    ActivitySource,
    ActorType,
    EventType,
    LedgerType,
    SubjectType,
)
from app.modules.activities.persistence.deal_stages import SqlAlchemyDealStageRecorder
from app.modules.activities.persistence.recorder import SqlAlchemyActivityRecorder

__all__ = [
    "ActivityActor",
    "ActivityEvent",
    "ActivityPayload",
    "ActivityRecorderPort",
    "ActivitySource",
    "ActorType",
    "CrmRecordPayload",
    "EventType",
    "LedgerRef",
    "LedgerType",
    "LinkedInScanPayload",
    "MatchDecisionPayload",
    "MatchRunPayload",
    "MeetingPayload",
    "NoPayload",
    "ProfileWritePayload",
    "SqlAlchemyActivityRecorder",
    "SqlAlchemyDealStageRecorder",
    "StageChangePayload",
    "SubjectType",
]
