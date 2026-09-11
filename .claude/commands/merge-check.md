Pre-Merge Checklist

Use this as the final engineering quality gate before a change is

considered merge-ready.

Workflow Position

This skill runs after /code-review, not before it and not

instead of it.

Implementation is complete.

/code-review runs and finds flaws in the code.

Flaws are fixed.

This checklist runs against the final state of the code — the

  last gate before merge.

If /code-review has not yet been run on this change, run it first.

Do not use this checklist as a substitute for code review — it

verifies safety and completeness of a change already reviewed for

flaws; it does not itself hunt for flaws the way code review does

(though the adversarial framing in Sections 1 and 9 means it will

still catch things code review missed).

Rule

Do not call the change merge-ready until all applicable checks pass.

The priority order is:

Correctness &gt; Security &gt; Data integrity &gt; Failure handling &gt;

Regression safety &gt; Type safety &gt; Maintainability &gt; Performance &gt;

Elegance

Do not optimize for architectural elegance while missing correctness,

security, or reliability.

0. Scope Calibration

Before running the checklist, classify the change so rigor matches

blast radius. Do not spend equal time on a one-line copy fix and a new

payment flow.

Classify as one of:

Trivial — copy/text change, styling-only tweak, comment/doc

update, no logic or contract change.

Moderate — logic change contained to one module, no new

external contracts, no DB schema change.

High-risk — touches auth, Attio/CRM writes, data integrity,

DB migrations, cross-module boundaries, or shared/widely-used

modules (utilities, attio, organizations, notifications).

Rules based on classification:

Trivial: Run Sections 1 (Correctness), 14 (Code Quality),

  and 15 (Final Merge Gate) only. State explicitly that the rest

  were skipped due to trivial scope.

Moderate: Run all sections, but architecture/abstraction

  sections (3-5) can be answered briefly if nothing changed

  structurally.

High-risk: Run every section in full. No section may be

  skipped or answered briefly.

State the chosen classification and reasoning as the first line of

output, before the results table.

1. Correctness

Adversarial stance: Assume the implementation is wrong until you

find evidence it is right. Do not confirm the happy path and stop —

actively try to construct an input, sequence, or timing that breaks

it. A checklist item is only "done" if you tried to break it and

failed, not merely if you didn't think of a way to break it.

Implementation satisfies the requirement/ticket.

Happy path has been tested.

Expected failure paths have been tested.

Empty, null, missing, and invalid inputs have been considered.

Boundary values have been considered.

Duplicate/repeated actions have been considered (Slack

  redelivers slash commands and interactions — idempotency guards

  matter here more than in a typical REST API).

Existing functionality has been checked for regressions.

The 3-5 most likely ways this could misbehave in production

  have been tested (a slow Bedrock/Firecrawl/Attio call, a stale

  Slack trigger_id, a concurrent write to the same organization).

2. Type Safety (Python + FastAPI)

🐍 Typing &amp; Data Validation

Request/response boundary types are explicit Pydantic models — never a bare dict/Any at a module or function boundary (this repo's ruff ANN rule and [CLAUDE.md](http://CLAUDE.md) both require this).

Optional/nullable fields are intentional and correctly modeled.

Type hints are present throughout meaningful application code.

Structural and field-level validation is handled by Pydantic models rather than scattered manual checks in route/handler code.

Ports at the application/ boundary are typing.Protocols and never expose ORM types — mapping happens in persistence/.

uv run ty check . passes with no new suppressions added to silence it.

⚡ Async &amp; Performance

async def handlers (Slack command/action handlers, FastAPI routes) do not perform blocking I/O such as time.sleep(), synchronous HTTP clients, synchronous DB calls, or blocking filesystem operations.

Blocking operations are moved to a sync path or explicitly offloaded from the event loop.

Async code uses async-compatible libraries for I/O (asyncpg/SQLAlchemy async engine, AsyncFirecrawl, boto3 calls wrapped in [asyncio.to](http://asyncio.to)_thread as the existing Bedrock clients already do).

Work that would overrun Slack's 3-second trigger_id/ack budget runs in a background task (InProcessTaskRunner) with a placeholder message updated afterward — not inline in the handler before ack()/before opening a modal.

CPU-intensive or heavy computation is not executed directly inside a request/event handler.

🛡️ Configuration &amp; Security

Configuration is managed through pydantic-settings ([config.py](http://config.py)::Settings) rather than scattered os.getenv() calls.

A new setting is added to the module's Settings class and server/.env.example, and to server/tests/test_env_[example.py](http://example.py)::_SETTINGS_CLASSES if it's a new module.

Required configuration values are validated at application startup (missing required Settings fields fail fast).

Secrets, credentials, API keys are not hardcoded or committed — they live in AWS Secrets Manager, never in *.tfvars or a committed .env.

🗄️ Database Management

Database engine/sessionmaker is not constructed per-request — each module's persistence/[database.py](http://database.py) @lru_caches it once.

Sessions are scoped correctly: a session backing one repository is not held open across an unrelated multi-second operation (see matching_engine's own documented session-lifetime pattern).

Writes that touch more than one repository go through that module's Unit of Work, not ad-hoc separate commits.

Schema changes go through an Alembic migration in server/alembic/ — never ad-hoc SQL or runtime DDL.

📜 Observability &amp; Error Handling

print() is not used for logging; the project's logging/configure_logging setup is used instead.

Logs contain useful contextual information (run id, org id, trigger, command) where appropriate.

Sensitive information (Slack tokens, Attio API keys, full prompt/response content) is not logged — existing Bedrock/Attio clients deliberately log metadata only; new logging should follow that precedent.

Exceptions are handled at the appropriate layer; broad except Exception exists only where the codebase's own pattern requires it (e.g. a background-task boundary that must never crash silently and must notify the user).

A Slack-facing failure results in a user-visible message (ephemeral or an updated placeholder), not a silently swallowed error.

🏗️ Layered Architecture

Route/handler code remains thin; business logic lives in application/.

Business logic is not duplicated across multiple handlers.

domain/ and application/ never import their own module's persistence/, providers/, api/, fastapi, pydantic, or sqlalchemy — verified by that module's own tests/test_[architecture.py](http://architecture.py).

Cross-module imports only reach another module's root **all** or its domain/ (shared-kernel exception) — never its persistence//providers//api/ unless that module is one of the documented full-access peers (utilities, attio, organizations).

New endpoints/handlers follow the existing project's router/dependency/service/model conventions for that module.

3. API Contract

Request shape is correct.

Response shape is correct.

HTTP method is appropriate (for the small internal REST surface — health/readiness, the desktop-app ingest endpoints, the Attio webhook).

HTTP status codes are appropriate.

Validation is enforced (Pydantic at the boundary).

Timeout/failure behavior of the calling side (Slack retrying a slow ack, the desktop app retrying an ingest call) is handled.

Authentication/signature verification is correct where it applies (Slack signing secret, Attio webhook signature, desktop app's shared key).

Breaking changes to a webhook/API shape have been identified and, if this repo's docs describe the contract, those docs are updated.

Pydantic models represent the intended contract exactly — no field silently reshaped between the API layer and persistence.

4. Architecture and Modularity

Ask whether the implementation belongs in an existing module or needs a

new module.

Prefer an existing module when:

It has the same responsibility.

It represents the same domain concept.

The existing module remains cohesive.

The module is not becoming a dumping ground.

Prefer a new module when:

It introduces a distinct responsibility.

It represents a different domain concept.

It has a different reason to change.

The existing module is already too complex.

Testing or dependency management would become difficult.

Ask:

If this feature changes six months from now, what else will I

accidentally have to touch?

Avoid both monolithic modules and unnecessary abstraction. Run

/modular-monolith for any change that adds a module or a cross-module

dependency — this checklist's Section 2 layering bullets are a summary,

not a replacement for that skill's full reconciliation pass.

5. DRY and Abstraction

Meaningful duplication has been identified.

Repeated logic with the same meaning is consolidated where

  appropriate.

Similar-looking code representing different business concepts

  has not been prematurely abstracted (e.g. buyer vs. seller fields

  that look alike but carry different vocabularies/ownership — see

  ddl_commands' FieldSpec seam for the deliberate exception where

  unification was warranted).

No generic abstraction was created solely to eliminate a small

  amount of duplication.

The chosen abstraction is simpler than the duplication it

  replaces.

Principle:

Duplication is cheaper than the wrong abstraction.

6. SOLID and Maintainable Design

Apply SOLID pragmatically.

Modules/classes have clear responsibilities.

Large functions/classes have been decomposed where useful.

Dependencies flow through sensible boundaries (Ports, not

  concrete imports, across a module boundary).

Business logic is separated from Slack/HTTP transport concerns

  where appropriate.

New abstractions (a new Port, a new mixin) have a concrete

  reason to exist.

No architecture has been introduced purely for theoretical

  compliance.

Avoid unnecessary interface/factory/helper layers for simple

functionality.

7. FastAPI / Slack-Bolt-Specific Checks

Prefer:

Handler (Slack command/action or FastAPI route) → Service (application/) → Repository/Provider

Handlers remain reasonably thin.

Business logic is not unnecessarily embedded in handlers.

Pydantic validation is used appropriately.

Response models are defined for any REST route.

Correct HTTP status codes are returned.

Slack request signature verification is intact (never bypassed

  "to make testing easier").

Attio webhook signature verification is intact.

Database access is appropriately isolated behind a repository/UoW.

Exceptions are handled consistently with the module's existing

  pattern (e.g. PartialWriteError's "what already landed" semantics

  in ddl_commands).

Sensitive information is not exposed in errors or ephemeral

  Slack messages sent back to the operator.

Blocking work is not accidentally performed in an async handler.

8. Error Handling and Failure Modes

Ask:

How does this fail?

Validation errors

Database failures

External API failures (Attio, Bedrock, Firecrawl, Slack itself)

Timeout (especially Slack's 3s trigger_id/ack budget)

Missing resources (org/role not found, run not found)

Permission/scope failures (Attio is_test scope mismatch)

Unexpected exceptions

Errors are not silently swallowed.

Errors are actionable — the operator sees a Slack message that

  tells them what happened, not just a generic failure.

Error behavior is consistent with existing application

  conventions (Attio-then-Postgres ordering, PartialWriteError,

  the _run() ack-timing wrapper pattern).

9. Security

Treat security checks as a hard merge gate.

Adversarial stance: Approach this section as an attacker, not as

the author. For every input boundary, ask "how would I abuse this?"

before asking "does this look fine?" A pass here means you tried to

defeat the control (bypass auth, inject, escalate privilege, leak

data) and could not — not that you reviewed the code and nothing

jumped out.

Slack request signatures are verified before any payload is trusted.

Attio webhook signatures are verified before any payload is trusted.

Input validation is enforced (Pydantic, plus Attio option/vocabulary validation before a write).

Injection risks have been considered (raw SQL in attio_[sync.py](http://sync.py)'s upsert paths, if touched).

ATTIO_IS_TEST scope is respected — a write never crosses from a test/dev instance into a production Attio record, or the reverse.

Sensitive fields (tokens, secrets, full LLM prompt/response content) are excluded from logs and from any Slack message.

Secrets use AWS Secrets Manager / environment configuration, never a literal in code or a committed file.

Logs do not expose credentials, tokens, or PII beyond what the existing modules already log.

10. Database and Data Integrity

Queries are correct.

Query performance is reasonable.

N+1 queries have been considered.

Appropriate indexes have been considered (e.g. the trigram GIN index used for org-name search).

Transactions/Unit-of-Work boundaries are used where a write touches more than one table.

Race conditions have been considered (concurrent /add-* on the same org — this repo's own answer is an explicit row lock, not just a unique constraint).

Database migrations are included when necessary, and uv run alembic check / alembic heads (single head) has been run.

Existing data remains compatible with the change.

Migration rollback/recovery has been considered for risky changes.

Concurrent requests cannot corrupt data.

Ask:

What happens if two requests execute this operation simultaneously?

11. Performance

Do not prematurely optimize, but check for obvious regressions.

Backend

Database query complexity is reasonable.

N+1 queries are avoided.

Blocking operations are not accidentally placed in async paths.

External calls (Attio, Bedrock, Firecrawl) have appropriate timeouts.

Large payloads are avoided where possible.

Expensive work is cached/batched where justified.

AI / External Services

Bedrock/Firecrawl calls have timeouts.

Retry behavior is intentional (bounded exponential backoff on transient errors only, not on validation failures).

Token/usage cost has been considered.

Concurrency limits have been considered where relevant (e.g. MAX_CONCURRENT_SUMMARIES-style semaphores).

Expensive inference is not accidentally repeated.

Failure of an LLM, Firecrawl, or Attio call is handled gracefully (fail soft and log, or fail closed with a clear message — matching the existing precedent for that call site).

12. Testing

Use risk-appropriate automated tests.

TDD is useful, but merge readiness is about sufficient behavioral

protection, not whether TDD was followed mechanically.

Unit tests

Important business logic is covered.

Edge cases are covered.

Validation and transformations are covered.

A new/changed module has its own tests/test_[architecture.py](http://architecture.py)

  passing (layering rule) — copied and prefix-renamed from an

  existing module's, not invented from scratch.

Integration tests

Where appropriate:

Handler → service → database behavior is covered.

External-service boundaries are tested via fakes (tests/fakes/), not real network calls.

A new module's integration test directory is added to server/[checks.sh](http://checks.sh)::integration().

Repo-wide fitness tests

server/tests/test_[architecture.py](http://architecture.py) (cross-module boundaries, **all**-only root imports, acyclic module graph) passes.

server/tests/test_env_[example.py](http://example.py) passes for any new/changed Settings class.

The test suite covers the highest-risk behavior (Attio-then-Postgres ordering, idempotency, scoring/dedupe logic) rather than chasing arbitrary coverage percentages.

13. Regression and Root Cause

For bug fixes:

Root cause has been identified.

The fix addresses the cause rather than only the symptom.

A regression test exists for the bug where appropriate.

Similar instances of the same bug pattern have been considered.

The fix does not introduce an equivalent issue elsewhere.

Ask:

Can this same class of bug occur somewhere else?

14. Comments and Documentation

Comments explain why, not obvious how.

Non-obvious business rules are documented.

Architectural constraints are documented where necessary.

External API quirks/workarounds are documented (Attio's

  option-ID wrapping, Bedrock's forced-tool-call parsing, etc.).

Important performance/security decisions are documented.

No obvious code is cluttered with unnecessary comments.

Stale comments have been removed or updated.

The affected module's README.md/HOW-TO-READ.md, [CHANGELOG.md](http://CHANGELOG.md), and any relevant docs/ page are updated in the same PR.

15. Code Quality

uv run ruff format --check . passes.

uv run ruff check . passes.

uv run ty check . passes.

uv run pytest (or the relevant server/[checks.sh](http://checks.sh) target) passes.

No dead code.

No unused imports.

No debug statements/logs.

No accidental commented-out code.

No unnecessary TODOs introduced.

Naming is clear.

Functions/classes are reasonably sized.

Magic numbers/constants are intentional and understandable.

No unnecessary dependency has been introduced.

16. CTO-Level Review

Everything above checks whether the code is correct and safe. This

section checks whether it's the kind of code that earns trust —

whether a demanding CTO reviewing this diff cold, with no context

except the ticket, would approve it without a follow-up meeting.

Read the diff once more with this specific lens. For each item, don't

just answer yes/no — write the one sentence that would justify the

answer out loud in a review.

Ownership test: If this breaks in production at 2am, would

  I be comfortable being the one paged for it? Is the failure mode

  debuggable from logs alone, or would whoever's on call be

  guessing?

Right problem test: Does this solve the actual problem, or

  a proxy for it? (e.g., catching a symptom instead of the cause,

  adding a flag instead of fixing the default, handling the ticket's

  literal words instead of its intent.)

Simplicity test: Is there a meaningfully simpler

  implementation that does the same job? If yes, why wasn't it used?

  A CTO will ask this; have the answer ready, not discovered live.

Silent cost test: Does this quietly increase on-call

  burden, infra cost, cognitive load for the next engineer, or

  coupling between modules? None of these show up as a failing test,

  but all of them show up as "why does this codebase feel worse than

  it did a year ago."

Confidence test: Am I proposing this because I verified it

  works, or because I ran out of things to check and it seems fine?

  A CTO can tell the difference between "I tested this" and "I

  didn't find a reason not to ship this" — the second one gets

  pushback every time.

Explain-it-back test: Could I explain, in two sentences and

  without hedging, why this change is safe to merge? If the

  explanation needs a paragraph of caveats, it's not ready.

If any test doesn't have a confident, specific answer, treat it the

same as a ❌ in the results table below — "I didn't think about it" is

exactly the gap a CTO-level review exists to catch, and it's cheaper

to catch here than in a review comment.

17. Final Merge Gate

Before declaring the task merge-ready, answer YES to all applicable

questions:

Does it satisfy the requirement?

Have I tested how it fails?

Are types and API/webhook contracts safe?

Is the code in the right module/layer?

Could it break existing behavior?

Did I introduce a security/privacy risk?

Did I introduce a data-integrity risk?

Did I introduce unnecessary expensive work (extra Attio/Bedrock/Firecrawl calls)?

Are important behaviors protected by automated tests, including

  the repo-wide and per-module architecture fitness tests?

Can production failures be diagnosed from logs alone?

Will another engineer understand and safely modify this six

  months from now?

If any answer is "I don't know", do not call it merge-ready yet.

Output Format

Report results as a markdown table, one row per section (not one row

per checkbox — a wall of checked boxes is not scannable). Skip rows

for sections excluded by Scope Calibration.

Section

Status

Notes

0. Scope Calibration

—

Classification: Moderate. Reasoning: touches one module, no schema change.

1. Correctness

✅

Tested happy path + 4 edge cases, including a duplicate Slack delivery.

2. Type Safety

✅

No bare dict/Any at a boundary. ty check clean.

3. API Contract

⚠️

Response shape correct; one status code review pending.

...

16. CTO-Level Review

⚠️

Simplicity test flagged: a helper could replace duplicated extraction logic. Not blocking but noted.

17. Final Merge Gate

❌

Not merge-ready: see Section 3.

Status legend:

✅ Pass — checked and verified, no issues.

⚠️ Pass with caveat — acceptable but worth flagging to the user

(e.g. a deliberate tradeoff, deferred work, minor nit).

❌ Fail — blocks merge-readiness. Must be listed with the specific

issue, not just marked failed.

— Not applicable / skipped per Scope Calibration.

After the table, if any row is ❌, list each failure as a short

actionable bullet (what's wrong, where, and what would fix it) rather

than leaving it implicit in the table's Notes column.

Do not declare the change merge-ready if any applicable row is ❌ or

if any item required to answer a row was genuinely unknown rather than

verified.

Completion Rule

/code-review is assumed to have already run before this skill

starts (see Workflow Position above) — do not ask the user whether to

invoke it; that step is upstream, not downstream, of this checklist.

Once all applicable checks above pass:

State plainly that the change is merge-ready, based on the

results table. No further action or confirmation is needed from the

user unless a row is ❌ or unresolved.

If any row is ❌, do not declare merge-ready — list the specific

failures (per the Output Format section) and stop there.