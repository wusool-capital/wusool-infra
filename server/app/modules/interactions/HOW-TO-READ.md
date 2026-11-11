# How to read `interactions`

A walkthrough for someone who has never seen this module. Only the domain
layer exists so far, and it is small, so start there.

## The one-sentence version

Turn a list of `Touch` rows (one email or meeting between a team member and
one outside contact) into the fields Attio shows for a Person or Organization.

## Read in this order

1. `domain/model.py`: the value types. `Touch` is the input, `InteractionSummary`
   the output, `ScoringRules` the tunables.
2. `domain/scoring.py`: `score_pair` is the whole connection-strength rule.
   `now` is a parameter so tests and the nightly pass use the same code.
3. `domain/summary.py`: `summarize` picks first, last and next dates, the last
   interaction's owner, and the strongest pair.
4. `domain/filters.py`: `is_ignored` decides what never counts.
5. `tests/unit/test_scoring.py`: the plan's worked example (Jules and Sara
   score 9.1, Strong; three quiet months later about 4.5, Good).

## Two things that are easy to miss

**Direction is relative to the team, not to the mailbox.** An email Jules sends
to Sara with Ramzy on CC is outbound in both mailboxes. Ramzy's copy has role
`cc`, which is what the owner rule uses to prefer Jules.

**Future meetings are not interactions yet.** `score_pair` and the "last"
dates ignore anything after `now`; only `next_*` reads them, and only within
the next 180 days.

## Why `domain/` imports no framework

`tests/test_architecture.py` fails if `domain/` or `application/` imports
`pydantic`, `sqlalchemy`, `fastapi`, or this module's own `persistence/`,
`providers/` or `api/`. Settings use pydantic, so they live in `config.py`
at the module root instead.
