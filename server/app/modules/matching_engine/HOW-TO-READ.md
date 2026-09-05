# How to read `matching_engine`

A walkthrough for someone who has never seen this module before. See
`README.md` first — its "Matching pipeline, in brief" section already
describes *what* each of the 8 steps does; this file is about *where the
code for each step lives*.

## The one-sentence version

One Slack command, `/find-match <buyer name>`, that resolves a buyer,
asks Bedrock to extract its structured requirements, filters and scores
every eligible seller deterministically (no LLM involved in the actual
numbers), asks Bedrock again for narrative reasoning on the shortlist,
persists the run, and posts an Approve/Reject message to Slack.

## Follow one request through the code

```
1. /find-match <buyer name>
   -> api/slack/handlers/commands.py
      - resolves the name (application/buyers.py's BuyersMixin), opens a
        "confirm this buyer" modal for ANY non-empty result — even one
        strong match needs an explicit confirm, since the actual
        workflow (Bedrock + scoring + persistence) is expensive

2. Confirm modal submitted
   -> api/slack/handlers/actions.py
      - dispatches the real work: application/matching/use_cases.py's
        MatchingMixin.run_match — this is the orchestrator, and it's
        deliberately Slack-independent (callable from a test the same way)

3. MatchingMixin.run_match, roughly in order:
   a. creates the run/header row and commits it immediately — queryable
      even if everything after fails
   b. Stage 0: requirement extraction (Bedrock, ONE call)
      -> application/requirements.py's BuyerRequirementExtractionService
         - builds the prompt from the buyer's investment_strategy/notes
           plus recent meeting notes (domain/meetings.py)
         - the Bedrock call itself, including the validate-repair-retry-
           then-fail-closed policy, lives behind a Port
           (application/ports/llm.py) — this service only owns prompt
           content, never talks to boto3 directly
      -> result: a domain/requirements.py RequirementProfile — hard
         requirements (can eliminate a candidate) and soft preferences
         (never eliminate, only weighted), each with provenance (was this
         a real CRM field, or something the LLM inferred from free text?)
   c. Stage 1 + Stage 2: filter and score every eligible seller
      -> domain/matching/scoring.py — PURE logic, no I/O at all. One
         function evaluates a candidate against one criterion; filtering
         and scoring both call that SAME function, so "would this
         eliminate the candidate" and "what's the sub-score" can never
         disagree with each other.
   d. Stage 3: reasoning (Bedrock, ONE call, top-N shortlist only)
      -> application/matching/reasoning_service.py's
         MatchReasoningService — same Port-based shape as step (b).
         Produces narrative only: it CANNOT change a score or invent a
         fact that wasn't already given to it in the prompt.
   e. persists match_scores + match_results rows + marks the run
      complete, all in ONE atomic transaction
      -> persistence/repositories/matching_repository.py, via a
         Unit-of-Work (persistence/unit_of_work.py)
   f. posts the ranked result to Slack (or, if every candidate scored
      too low, up to 3 unverified web leads via providers/firecrawl/
      instead) -> api/slack/views/match_result.py

4. Approve/Reject button clicked
   -> api/slack/handlers/actions.py -> application/approvals.py
      - re-validates the record's CURRENT state against the database —
        never trusts what the Slack payload claims the state is — and
        does an atomic compare-and-set so two concurrent decisions can't
        race each other
```

If you read nothing else, read `application/matching/use_cases.py`
(`MatchingMixin.run_match`) — it IS the pipeline; every other file exists
to support one step of it.

## The domain concept worth understanding: `CRITERION_REGISTRY`

`domain/matching/scoring.py`'s `CRITERION_REGISTRY` is the single list of
criterion names this engine actually knows how to check against real
seller data (revenue, sector, geography, and so on). It matters because
`application/requirements.py`'s extraction prompt is built FROM this same
registry (`describe_criteria`) — the LLM is only ever told about criteria
this engine can evaluate, and can never invent a criterion name that has
nothing behind it. If you're adding a new checkable requirement, this
registry is where you start, not the prompt.

## Why two Bedrock-calling services aren't mixins

`README.md`'s Structure section already flags this, but it's worth
repeating because it's a real pattern you'll see again in `meetings`:
`BuyerRequirementExtractionService` (step 3b) and `MatchReasoningService`
(step 3d) are standalone collaborator objects, constructed once and handed
to `MatchingMixin`, NOT mixins on `ServiceBase` like `BuyersMixin`/
`ApprovalsMixin`/`MatchingMixin` are. The distinction: a mixin holds
state every use case in the facade might need; these two are only ever
called from inside `run_match`'s own steps, so forcing them into the
shared-constructor shape would just add unused state to every other
mixin's `__init__`. See `application/base.py`'s docstring for the fuller
explanation of why this module's `ServiceBase` isn't as uniform as
`ddl_commands`'s.

## The Bedrock Port's job vs. the application service's job

Both `BuyerRequirementExtractionService` and `MatchReasoningService` say
the same thing in their docstrings, and it's a useful rule to internalize:
**the Port (`application/ports/llm.py`, implemented by
`providers/bedrock/client.py`) owns the mechanics of getting a valid
response out of Bedrock** — retry on failure, one repair attempt on a
malformed response, fail closed if that also fails. **The application
service only owns the actual prompt content** — what to ask, how to
build a repair prompt when the first attempt came back wrong. If you're
fixing "Bedrock returned garbage," look in `providers/bedrock/client.py`.
If you're fixing "the LLM keeps getting the wrong idea," look in
`application/requirements.py` or `application/matching/reasoning_service.py`.

## Where to go next

- Changing which requirements can be checked → `domain/matching/scoring.py`'s
  `CRITERION_REGISTRY`.
- Changing the requirement-extraction or reasoning prompts →
  `application/requirements.py` / `application/matching/reasoning_service.py`.
- Changing how a score is computed → `domain/matching/scoring.py` (pure,
  easy to unit test in isolation).
- The web-fallback lead search (when nobody scores well enough) →
  `application/web_search.py`, `providers/firecrawl/client.py`.
- The approval/rejection state machine → `domain/matching/lifecycle.py`
  (`can_transition`), `application/approvals.py`.
