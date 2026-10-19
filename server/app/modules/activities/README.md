# activities

The business-event index. Every meaningful event (a Slack seller add, a match
approval, a deal stage change, a published meeting, a lead-magnet submission)
becomes one `activities` row. The detail stays in the domain ledger the row
links to. See [the audit](../../../../docs/internal/dev/ACTIVITIES_AUDIT.md)
for why.

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

```
activities/
  __init__.py                       # __all__: the public contract below
  domain/vocabulary.py              # SubjectType, EventType, ActorType, ActivitySource
  domain/payloads.py                # typed payload models, one per event shape
  domain/event.py                   # ActivityActor, ActivityEvent
  application/ports/recorder.py     # ActivityRecorderPort Protocol
  persistence/recorder.py           # SqlAlchemyActivityRecorder
  persistence/deal_stages.py        # SqlAlchemyDealStageRecorder (deal_stage_events + deal.stage_changed)
```

## Rules

- **Link, don't copy.** `ActivityEvent` takes at most one ledger link
  (`tool_run_id`, `match_result_id`, `meeting_id`, `command_run_id`,
  `deal_stage_event_id`, `signal_id`). `payload` holds only the event's own
  facts, and field names rather than values for anything that can hold PII.
- **`ts` is event time**, `created_at` is insert time. Leave `occurred_at`
  unset unless the event happened earlier than the write.
- **Actor.** `actor_type` is always set. `actor_ref` is the raw id (Slack user,
  Attio member/token, Scribe install, process name). `actor_attio_id` is set
  only for an Attio member that exists in `users`; there is no Slack-to-`users`
  mapping.
- **Idempotency.** A writer with a stable id sets `idempotency_key`, for example
  `match.approved:{match_result_id}`; a repeat is dropped by the partial unique
  index. Webhook rows have no stable event id and set none.
- **Never aborts the caller.** `SqlAlchemyActivityRecorder.record` writes inside
  a savepoint and swallows and logs any error. Pass it the same session as the
  business write.
- **Not a raw audit log.** Raw Attio deliveries go to `attio_raw_events`.

## Public contract

`from app.modules.activities import ...`: `ActivityEvent`, `ActivityActor`,
`ActivityRecorderPort`, `SqlAlchemyActivityRecorder`, the vocabulary enums and
the payload models in `__all__`. Application code depends on
`ActivityRecorderPort`; the persistence layer constructs
`SqlAlchemyActivityRecorder(session)`.

Adding an `EventType` needs no migration (the database checks only the
`domain.verb` format). Adding an `ActorType` or `SubjectType` needs a CHECK
migration; a unit test fails if the enums and the model's CHECKs drift.

## Testing

`tests/unit` covers the vocabulary, payload round-trips and event validation.
`tests/integration` covers the recorder against Postgres. `tests/test_architecture.py`
keeps `domain/` and `application/` free of `persistence/`, `fastapi`, `pydantic`
and `sqlalchemy`.

## Where to go next

New to this module? See [`HOW-TO-READ.md`](HOW-TO-READ.md).
