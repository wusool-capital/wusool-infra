# How to read `meetings`

This is a walkthrough for someone who has never seen this module before.
It doesn't cover everything — see `README.md` for scope and
`HOW-TO-TEST.md` for running it — it just gets you to the point where the
file tree stops looking like a maze.

## The one-sentence version

The WusoolScribe desktop app records and transcribes a meeting **locally**,
then pushes the transcript here. This module turns that transcript into a
structured summary (via AWS Bedrock), stores it, and optionally files a
note in Attio. That's the whole job — no recording, no transcription, no
Slack.

## Start here: follow one request, not the folders

The fastest way to understand a layered codebase is to trace one real HTTP
request end to end, then go back and read each stop more slowly. Here's the
one to trace: **the desktop app pushes a transcript.**

```
1. POST /desktop/meetings arrives
   -> api/auth.py           checks the Bearer token
   -> api/ingest.py         the route handler

2. api/ingest.py:
   - rejects an oversized transcript (422) before touching anything else
   - builds "which of the 5 roles (seller/buyer/investor/internal/general)
     did the desktop app tag?" into two small dicts
   - calls service.ingest_meeting(...)          <- into application/

3. application/ingest.py (IngestMixin.ingest_meeting):
   - checks (install_id, local_recording_id) hasn't been pushed before
     -> 409 if it has (never silently re-summarize a re-push)
   - resolves each tagged role to a real Attio org, a free-text name,
     or rejects a stale reference               <- persistence/organization_lookup.py
   - picks ONE primary role (seller > buyer > investor > internal > general)
     and stashes the rest for later              <- domain/roles.py
   - writes the `meetings` row with status="summarizing"
                                                  <- persistence/meetings_repository.py
   - returns to api/ingest.py WITHOUT summarizing anything yet

4. api/ingest.py:
   - schedules the actual summarization as a FastAPI BackgroundTask,
     via bootstrap.run_summarize_and_publish (NOT service.summarize_and_
     publish — see "The one gotcha" below)
   - returns 201 immediately — the desktop app never waits on Bedrock

5. (some time later, in the background)
   bootstrap.run_summarize_and_publish
   -> application/publish.py (PublishMixin.summarize_and_publish):
      - loads the meeting back
      - calls application/summarize.py (SummarizationService.summarize)
        -> which chunks the transcript if it's long   <- domain/chunking.py
        -> builds the actual LLM prompt                <- domain/prompts.py
        -> calls the Bedrock client                     <- providers/bedrock/client.py
      - renders the result to plain text                <- domain/rendering.py
      - writes it back to the `meetings` row (status="completed")
      - if there's a resolved org, files a note in Postges and,
        if configured, in Attio too                     <- providers/attio/note_writer.py

6. The desktop app polls GET /desktop/meetings/{id} until status
   isn't "summarizing" anymore, and gets the summary back.
```

If you read nothing else in this file, read `application/ingest.py` and
`application/publish.py` — that IS the module. Everything else exists to
support those two files.

## The five layers, and what each one is *for*

This module follows the repo-wide "modular monolith" layering
(`docs/dev/MODULAR_MONOLITH_GUIDE.md`). If you already know that guide,
skip this section. If you don't, here's the one-line job of each folder,
in the order data flows through them:

| Folder | Job | Can talk to |
|---|---|---|
| `api/` | HTTP in, HTTP out. Auth, request/response shapes. | everything |
| `application/` | The actual business logic — "what happens when a transcript arrives." | only `domain/` and `application/ports/*` |
| `domain/` | Pure rules and data shapes. No database, no HTTP, no AWS SDK. | nothing else in this module |
| `persistence/` | Talks to *our* Postgres. | `domain/` |
| `providers/` | Talks to *someone else's* API (Bedrock, Attio). | `domain/` |

The rule that matters most: **`application/` never imports `persistence/`
or `providers/` directly.** It only knows about `application/ports/*.py`
(abstract interfaces — "something that can look up an organization,"
not "the Postgres table that stores organizations"). The real
implementations get handed to `application/` by `bootstrap.py`. This is
why you'll see a lot of "Protocol" classes in `application/ports/` that
look like they do nothing — they're contracts, not code. `tests/
test_architecture.py` enforces this mechanically; if you violate it, a
test fails, not just a code review.

`bootstrap.py` is the one file allowed to break that rule — it's the
*composition root*, the one place that says "here is the REAL Bedrock
client, here is the REAL Postgres repository, now wire them into the
business logic." If you're wondering "where does X actually get
constructed?", the answer is always `bootstrap.py`.

## A tour of every file, grouped by what it does

### The actual logic (`application/`)

- **`ingest.py`** — turns a desktop push into a `meetings` row. Read this
  first.
- **`publish.py`** — turns a `meetings` row into a finished summary + note.
  Read this second.
- **`status.py`** — backs the two "poll for status" endpoints. Also owns
  **stalled-meeting recovery**: if a background summarization crashed or
  the process restarted mid-flight, a stuck meeting recovers itself the
  next time the desktop app polls — no separate cron job, no queue.
- **`summarize.py`** — the actual "call the LLM, possibly more than once
  for a long transcript" orchestration. Short transcripts get one call;
  long ones get split into chunks, each summarized separately, then
  merged into one final summary.
- **`base.py`** — every one of the three classes above (`IngestMixin`,
  `StatusMixin`, `PublishMixin`) is combined into one `MeetingsService`
  in `service.py`. `base.py` is just their shared constructor — the thing
  that holds "here are the repositories/clients this service needs."
  You'll never call `IngestMixin` directly; you always go through
  `MeetingsService`.
- **`errors.py`** / **`provider_errors.py`** — the exceptions this module
  raises. `errors.py` is domain-facing (409 duplicate push, 404 not
  found, 422 bad company reference) and gets turned into the right HTTP
  status automatically. `provider_errors.py` is just the one
  Bedrock-specific failure.
- **`ports/`** — the abstract interfaces described above. Skim these to
  learn the *shape* of what each dependency can do, without caring how.

### The rules and data shapes (`domain/`)

- **`roles.py`** — the "seller/buyer/investor/internal/general" concept.
  Which role wins if a meeting is tagged with more than one, and the
  functions that encode/decode that choice into the database.
- **`summary.py`** — the 9-field shape of a finished summary (`title`,
  `executive_summary`, `decisions`, `action_items`, etc.) as plain Python
  dataclasses. This is the type everything downstream works with.
- **`prompts.py`** — the actual text sent to the LLM. This is the biggest
  file in the module (~900 lines) and it looks intimidating, but it's
  almost entirely prose: the system prompt, worked examples, and a very
  deliberate set of instructions for handling an unreliable transcript
  (see "Why the prompt is so paranoid" below). You don't need to read all
  of it to work on this module — you need it when you're changing what
  the summary looks like.
- **`chunking.py`** — splits a long transcript into LLM-sized pieces.
  Small and self-contained.
- **`rendering.py`** — turns the structured 9-field summary back into
  plain text (for the `meetings.summary` column) and turns a transcript's
  turns back into "Speaker: text" lines.

### Talking to our own database (`persistence/`)

- **`meetings_repository.py`** — every read/write against the `meetings`
  table this module needs: create, mark completed/failed, the stalled-
  recovery query, the cheap "just give me statuses" listing.
- **`notes_repository.py`** — writes to the `notes` table.
- **`organization_lookup.py`** — looks up/searches Attio organizations
  (via the shared `organizations` module — this module doesn't own that
  table, it just borrows the search).
- **`mappers.py`** — converts a raw database row into the typed
  dataclasses from `domain/`. This is the one place a database row and a
  Python type actually meet.
- **`database.py`** — boilerplate: how to get a database session.

### Talking to someone else's API (`providers/`)

- **`bedrock/`** — calls AWS Bedrock to actually run the LLM.
  `client.py` is the interesting one (retry logic, timeout handling,
  forcing the model to return well-shaped JSON); `boto_client.py` and
  `schemas.py` are supporting plumbing.
- **`attio/note_writer.py`** — files a note in Attio's CRM. Failure here
  is never allowed to fail the meeting itself — see its docstring.

### The HTTP surface (`api/`)

- **`router.py`** — the one file that combines every endpoint below into
  the thing `server/main.py` actually mounts.
- **`ingest.py`** / **`status.py`** / **`sync.py`** / **`companies.py`** —
  one file per endpoint. Each is short — read one, you've basically read
  them all.
- **`auth.py`** — the Bearer-token check every endpoint requires.
- **`schemas.py`** — the request/response JSON shapes. These exist to
  match the desktop app's existing client exactly, byte for byte — don't
  "clean these up" without checking what the client actually sends.
- **`dependencies.py`** — small FastAPI wiring glue (how a request gets a
  database session and a `MeetingsService`).

### Everything else

- **`bootstrap.py`** — described above: constructs the real repositories/
  clients and wires them into `MeetingsService`. Also owns
  `run_summarize_and_publish` (see the gotcha below).
- **`config.py`** — every environment variable this module reads.

## The one gotcha worth knowing before you touch anything

**A request's database session is not the same session a background task
should use.** `api/ingest.py` and `api/status.py` schedule summarization
via `bootstrap.run_summarize_and_publish`, never via
`service.summarize_and_publish` directly — the `service` object handed to
an endpoint is tied to that request's session, which is already committed
and closing by the time a scheduled background task actually runs.
`run_summarize_and_publish` opens its own session instead. If you ever see
`service.summarize_and_publish` being handed to `BackgroundTasks`
somewhere, that's a bug, not a shortcut — see `bootstrap.py`'s docstring
for the full explanation.

## Why the prompt is so paranoid (`domain/prompts.py`)

Two things about the input make the prompt unusually defensive, and it's
worth knowing both before you touch that file:

1. **Speaker labels are not reliable identities.** The desktop app has no
   real speaker diarization — every turn just says `"Participant"`. The
   prompt explicitly tells the model never to guess who said what based
   on a label, and to attribute by role ("the seller", "the buyer") or not
   at all when it can't tell.
2. **The transcript is untrusted input, not an instruction.** A meeting
   transcript could contain text that looks like a command ("ignore your
   previous instructions..."). The prompt wraps the transcript in
   delimiter markers and explicitly tells the model to treat anything
   inside them as content to summarize, never as something to obey.

If you're adding a new field to the summary or changing the wording, these
two constraints are the ones most likely to matter — grep for
`_SPEAKER_LABEL_RULE` and the `@@@TRANSCRIPT_START@@@`-style delimiters to
find where they're enforced.

## Where to go next

- Changing what gets summarized or how → `domain/prompts.py`,
  `application/summarize.py`.
- Changing what happens on push → `application/ingest.py`.
- Changing the wire format → `api/schemas.py` (but check the desktop
  app's client first — see that file's own docstring).
- Adding a new field to the summary → `domain/summary.py`,
  `providers/bedrock/schemas.py`, `api/schemas.py`, `domain/rendering.py`
  — in that order, since each one depends on the shape of the last.
- Running/testing any of this → `HOW-TO-TEST.md`.
