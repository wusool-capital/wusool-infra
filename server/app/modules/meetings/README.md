# Meetings

Ingests meeting transcripts pushed by the WusoolScribe desktop app,
summarizes them via AWS Bedrock, and writes the existing `meetings`/`notes`
tables. Optionally pushes the resulting note to Attio when
`ATTIO_NOTE_OBJECT_SLUG` is set.

This replaces Scribe's entire server-side pipeline (SQS, worker containers,
faster-whisper, its own Postgres) for the one thing the desktop app still
needs from a server: turning an already-recorded, already-locally-
transcribed meeting into a structured summary. The desktop app itself is
unchanged — it still records and transcribes locally and only pushes a
finished transcript here; recording/audio storage (S3) is out of scope, and
so is Slack delivery (the desktop app displays the summary itself).

Async contract, no queue: `POST /desktop/meetings` acks fast (row created,
`status=summarizing`) and schedules the actual Bedrock call as a FastAPI
`BackgroundTask` — no SQS, no separate worker process. The desktop app's
existing poll-and-sync behavior (`GET /desktop/meetings/{id}`,
`GET /desktop/meetings?install_id=`) is unchanged, and doubles as this
module's stalled-summarization recovery: both read paths attempt a
conditional `recover_stalled` flip and reschedule the background task if a
row has sat in `summarizing` past a timeout (see `application/status.py`).

Caddy's request timeout is a non-issue here: the HTTP response to the
desktop app's push returns before the Bedrock summarization call starts, so
there's no long-request-behind-a-proxy timeout to work around.

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

```
meetings/
  bootstrap.py       # composition root — build_* factories, no create_app()
  config.py           # Settings (pydantic-settings)
  domain/             # roles, MeetingSummary/SummaryNote, chunking, prompts,
                       #   rendering — framework-free, ported from Scribe
  application/        # ServiceBase + IngestMixin/StatusMixin/PublishMixin
                       #   (MeetingsService facade), SummarizationService,
                       #   application/ports/ Protocols
  persistence/        # SQLAlchemy repositories for meetings/notes,
                       #   organization lookup (wraps `organizations`)
  providers/          # bedrock/ (forced-tool-call Converse client, its own
                       #   300s-timeout boto client — deliberately not
                       #   shared with matching_engine's), attio/ (note push)
  api/                # router.py facade + one file per desktop endpoint,
                       #   Bearer DESKTOP_API_KEY auth
  tests/
```

Deliberately NOT wired to `matching_engine` — that module keeps reading
`meetings.summary`/`meetings.org_id` directly through the shared
`app.models.Meeting` ORM model, which is already the seam between the two.

## Database

Connects to the shared `wusool_crm` PostgreSQL database (models in
`app/models/`, migrations in `alembic/`). This module never creates tables
or runs migrations itself. Reads/writes the existing `meetings` and `notes`
tables through its own repositories only.

## Setup

Config comes from the repo-root `server/.env` (see `.env.example` there).
Relevant variables: `DATABASE_URL`, `DESKTOP_API_KEY`, `AWS_REGION`,
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (optional — omit to use the
standard AWS credential provider chain), `AWS_BEDROCK_MODEL_ID`,
`SUMMARY_MAX_TOKENS`/`SUMMARY_MAX_TOKENS_PER_CHUNK`,
`MAX_CONCURRENT_SUMMARIES`, `MAX_TRANSCRIPT_CHARS`,
`ATTIO_NOTE_OBJECT_SLUG` (optional — omit to skip pushing notes to Attio).

## Where to go next

New to this module? See [`HOW-TO-READ.md`](HOW-TO-READ.md). Running or
testing it? See [`HOW-TO-TEST.md`](HOW-TO-TEST.md).
