# Modular Monolith Guide

For developers new to this codebase's architecture. `server/` is **one**
deployed process, but internally it's split into independent modules under
`server/app/modules/` — each one structured like its own small application.
This doc explains the mental model, the folder layout, and how to actually
read a module. It assumes no prior exposure to the pattern.

## Why split a single process into modules at all?

The bot only needs to run as one process (Slack requires one Interactivity
URL per app — see [`server/README.md`](../../server/README.md)). But
`/find-match`'s matching pipeline and `/edit-buyer`'s Attio-sync logic don't
share any business rules, and mixing their code together in one folder
would make each harder to change without breaking the other. A "modular
monolith" keeps the single deployable process, but draws firm internal
walls between unrelated pieces of business logic — each module owns its
own rules, its own tables, its own external API calls — so changing one
can't accidentally break another. It's also what lets `matching_engine` and
`ddl_commands` be tested, and reasoned about, completely independently.

## The layers inside one module

A module is split into folders by **what kind of code it is**, not what
feature it belongs to. Open any module (e.g. `matching_engine/`) and you'll
find the same five folders:

| Folder | What lives here | Can import |
| --- | --- | --- |
| `domain/` | Pure business rules — plain Python classes, no framework. The actual "what does a match score mean" logic. | Nothing but the standard library (and, rarely, another module's `domain/`). |
| `application/` | Use cases — orchestrates a request end to end ("run a match", "edit a buyer"). Talks only through **Ports** (see below), never to a real database or API. | `domain/` and its own `application/ports/`. |
| `persistence/` | Talks to **our own** Postgres tables. SQLAlchemy lives only here. | `domain/`, `application/ports/`. |
| `providers/` | Talks to **someone else's** API (Attio, Bedrock, Slack). | `domain/`, `application/ports/`. |
| `api/` | The entry point — FastAPI routes, Slack command/action handlers, the Pydantic schemas at the HTTP/Slack boundary. | Everything else in its own module. |

Two more folders you'll see: `bootstrap.py` (the only place that's allowed
to construct a real repository or API client and wire it into a use case —
everywhere else takes these as injected arguments) and `scripts/` (one-off
or scheduled admin jobs, like the nightly Attio resync).

## The one rule that matters most: dependencies point inward

`domain/` knows nothing about Postgres, Attio, or even Pydantic — it's just
business rules in plain Python. `application/` knows a use case needs "a
buyer repository", but never imports the real SQLAlchemy class that
implements one — it depends on a **Port** instead (a `typing.Protocol`
under `application/ports/`, basically an interface: "anything with a
`get_by_id` method"). `persistence/`/`providers/` write the real classes
that satisfy those Ports. `bootstrap.py` is the only file that ever
imports both a Port and its real implementation together, to wire them up.

Why bother? Because it means `application/`'s logic can be tested against a
fake repository with zero real Postgres, and because it makes it obvious
where to look when something needs to change: business rule → `domain/`,
new use case → `application/`, new query → `persistence/`, new vendor call
→ `providers/`, new Slack command → `api/`.

## How to read a module in 5 minutes

Worked example: `/find-match <buyer>` in
[`matching_engine`](../../server/app/modules/matching_engine/).

1. **`api/slack/handlers/commands.py`** — the Slack command lands here
   first. It parses the command text and calls into `application/`.
2. **`application/matching/use_cases.py`**'s `RunBuyerSellerMatchUseCase` —
   the orchestrator. It calls the buyer-extraction service, the candidate
   retriever, the scoring engine, and the reasoning service in order — but
   only through their Ports, never the real classes.
3. **`domain/matching/scoring.py`** — the actual scoring/filtering rules,
   pure functions, zero I/O. This is the part you'd read to understand "how
   does a match score get computed", independent of Slack or Postgres.
4. **`persistence/repositories/matching_repository.py`** — the concrete
   class that satisfies `application/ports/matching.py`'s
   `MatchResultRepositoryPort`, doing the actual SQLAlchemy queries.
5. **`providers/bedrock/client.py`** — the concrete class that satisfies
   `application/ports/llm.py`'s `BedrockClient` Port, doing the actual AWS
   Bedrock API call.
6. **`bootstrap.py`** — where 2-5's concrete classes actually get
   constructed and handed to the use case from step 2.

Start at `api/` and follow the Port names into `application/ports/` to find
the real implementation in `persistence/`/`providers/` — that's the whole
navigation trick.

## Rules for talking between modules

A module almost never needs to reach into another module directly.
`ddl_commands` and `matching_engine` both need the shared `Organization`
entity, for example — instead of one importing the other, both import from
[`organizations`](../../server/app/modules/organizations/), a small shared
module. The rules:

- Import another module's `domain/` freely — it's pure logic with no
  framework dependency, safe to reuse.
- Import another module's root (`from app.modules.organizations import
  OrganizationRepository`) — but **only** names that module's own
  `__init__.py` explicitly exports via `__all__`. That list is the
  module's public contract; anything not in it is internal.
- Never reach into another module's `persistence/`, `providers/`, or `api/`
  directly — go through its `__all__` facade instead.
- Three modules (`utilities`, `attio`, `organizations`) are documented,
  deliberate exceptions to that last rule: they're pure infrastructure with
  no business logic of their own, so their whole surface is meant to be
  used directly. This is written explicitly in each of their own
  `__init__.py` docstrings — it's not a loophole, it's a stated design
  choice.

## How this is enforced (not just documented)

Every module has its own `tests/test_architecture.py` that scans its actual
Python imports and fails the build if `domain/`/`application/` import
anything they shouldn't (Postgres, FastAPI, another module's internals).
`server/tests/test_architecture.py` does the same check across module
boundaries. These run in CI on every PR — if one fails, the fix is almost
always to move the offending code to the right layer, not to weaken the
test.

## Quick reference: where does my code go?

| I'm writing... | It goes in... |
| --- | --- |
| A calculation, rule, or decision that doesn't touch a database or network | `domain/` |
| A new use case / workflow step | `application/<concept>.py` |
| An interface a use case needs, without deciding how it's implemented | `application/ports/<concept>.py` |
| A new database query on our own tables | `persistence/repositories/` |
| A call to Attio, Bedrock, Slack, or any other vendor API | `providers/<vendor>/` |
| A new Slack command, HTTP route, or request/response schema | `api/` |
| Wiring a new concrete class into a use case | `bootstrap.py` |

For the full, exhaustive rule set (used when reviewing PRs for layering
correctness), see the `/modular-monolith` skill referenced in `CLAUDE.md` —
this guide is the short version for getting oriented, that one is the
complete reference.
