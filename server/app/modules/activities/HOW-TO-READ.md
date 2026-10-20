# How to read `activities`

1. `domain/vocabulary.py` — the closed lists of event types, actors, subjects and sources.
2. `domain/event.py` — `ActivityEvent`, the one object a writer builds, and the
   the one check it enforces (a subject).
3. `domain/payloads.py` — the typed payload for each event shape.
4. `persistence/recorder.py` — the single INSERT, the savepoint, and the
   idempotency `ON CONFLICT`.
5. `../../models/activity.py` — the table, its CHECKs and indexes.

To record a new event: pick or add an `EventType`, build an `ActivityEvent` with
the right `ActivityActor` and ledger link, and `await recorder.record(event)` on
the business write's own session.
