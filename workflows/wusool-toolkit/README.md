# Wusool Toolkit Bot

One Slack bot, one process, one token — five commands:

- `/find-match <buyer name>` — the buyer-seller matching workflow
  (`matching-engine/`).
- `/edit-seller <name>`, `/edit-buyer <name>` — edit buyer/seller (and their
  organization's) profile fields. Writes to DEV Attio first, then Postgres —
  see `ddl-commands/README.md` for the full flow and why. `/remove-seller`/
  `/remove-buyer` don't exist (see ddl-commands' README, "History").
- `/add-seller <org name>`, `/add-buyer <org name>` — create a new
  seller/buyer role, searching for an existing organization first (attach
  to it) and creating a brand new one only if nothing matched. Same
  Attio-first principle as the edit commands, extended to creates — see
  ddl-commands' README, "The add flow".

`matching-engine/` and `ddl-commands/` are separate folders for functional
modularity only — they are **not** separately deployed. The root `main.py`
is the one real entrypoint: it builds a single Slack `AsyncApp`, registers
both folders' command/action/view handlers against it, and serves one
`POST /slack/events`. Neither folder's own `app/main.py` /
`ddl_commands/main.py` is used to run this bot — those still exist (each
folder's own test suite imports its own standalone app), but the root
`main.py` is what's actually deployed.

## Why two folders, one process

Slack ties one bot identity to one Slack App — one bot token, one signing
secret, and critically, **one Interactivity & Shortcuts Request URL for the
whole app** (not per-command). Almost everything past the initial slash
command — every modal, every button — is interactivity. Two independently
deployed services can't both be "the" interactivity target of one Slack app
without something routing between them, so this bot runs as one process.

Two real collisions had to be resolved to make that safe, not just wired
together:

- Both folders' Python code was named the top-level package `app` — only
  `ddl-commands/`'s was renamed, to `ddl_commands/` (matching-engine's own
  `app/` package is untouched, exactly as it was before this merge).
- Both folders separately registered a Slack `callback_id` of
  `"buyer_selection_modal"` for two different modals. `ddl-commands`' copy
  was renamed to `"buyer_role_selection_modal"` (and its seller sibling to
  `"seller_role_selection_modal"`, for a consistent naming convention).
  `tests/integration/test_merged_command_dispatch.py` at the repo root
  asserts this routes correctly and stays that way.

Each folder keeps its own independent SQLAlchemy `Base`/ORM models — this is
safe (SQLAlchemy has no single global mapper registry), and avoids ever
having to reconcile two independently-evolved `SellerRole`/`BuyerRole`
classes into one.

## Setup

```bash
cd workflows/wusool-toolkit
uv sync            # installs both matching-engine and ddl-commands into one venv (uv workspace)
cp .env.example .env  # then fill in real values — one shared Slack token/secret for both
```

## Running

```bash
uv run uvicorn main:app --reload
```

or via Docker Compose (builds one image from the root `Dockerfile`, alongside
a throwaway local Postgres, then upgrades its flat-SQL baseline through
Alembic before starting the bot):

```bash
docker compose up --build
```

- `GET /health` — liveness, no database dependency.
- `GET /readiness` (alias `GET /ready`) — confirms database connectivity.
- `POST /slack/events` — the one Slack callback endpoint for all 5 commands.
  Signature-verified by Bolt.

### Configuring the Slack app

One Slack app for all 5 commands — see `docs/SLACK_APP_SETUP.md` at the repo root
for the full checklist (Slash Commands table, Interactivity URL, OAuth
scopes, signing secret). `ddl-commands` also needs `ATTIO_API_KEY` (DEV
Attio write access) alongside the shared Slack credentials.

## Testing

```bash
uv run pytest
```

Runs this root's own merged-dispatch suite
(`tests/integration/test_merged_command_dispatch.py` — proves the two
collisions above stay fixed) plus, if run from within each subfolder, that
folder's own business-logic/wiring suite (`matching-engine/tests/`,
`ddl-commands/tests/`) unchanged from before this merge.

## Layout

```
workflows/wusool-toolkit/
├── main.py              # the real entrypoint — builds the one AsyncApp
├── pyproject.toml        # uv workspace root (members: matching-engine, ddl-commands)
├── Dockerfile             # the one deployed image
├── docker-compose.yml     # local dev: this bot + a throwaway Postgres
├── tests/                 # merged-app dispatch tests only
├── matching-engine/       # /find-match — see matching-engine/README.md
└── ddl-commands/          # /edit-seller, /edit-buyer, /add-seller, /add-buyer — see ddl-commands/README.md
```

See `database/README.md` (repo root) for the shared schema, and each
folder's own README for module-specific detail (matching-engine's Bedrock
config, ddl-commands' soft-delete/sync-guard design).
