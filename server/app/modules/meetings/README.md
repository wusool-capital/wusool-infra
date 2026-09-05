# Meetings

Ingests meeting transcripts pushed by the desktop app, summarizes them via
AWS Bedrock, and writes the existing `meetings`/`notes` tables. Optionally
pushes the resulting note to Attio when `ATTIO_NOTE_OBJECT_SLUG` is set.

Out of scope: no Slack surface, no S3/recordings storage. This module
replaces Scribe's server-side summarization step only — the desktop app
itself is unchanged and out of scope.

Caddy's request timeout is a non-issue here: the HTTP response to the
desktop app's push returns before the Bedrock summarization call starts, so
there's no long-request-behind-a-proxy timeout to work around.

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

```
meetings/
  bootstrap.py       # composition root — build_* factories (phase-core)
  config.py           # Settings (pydantic-settings)
  domain/             # entities, transcript/summary logic — framework-free
  application/        # use cases + application/ports/ Protocols
  persistence/        # SQLAlchemy repositories for meetings/notes
  providers/          # bedrock/ (summarization), attio/ (note push)
  api/                # router.py, dependencies.py
  tests/
```

Skeleton only at this stage — no business logic yet.

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

## Testing

```bash
uv run pytest
```
