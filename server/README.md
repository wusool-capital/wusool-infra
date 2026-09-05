# Wusool Toolkit Bot

One Slack bot, one process, one token — five commands:

- `/find-match <buyer name>` — the buyer-seller matching workflow
  (`app/modules/matching_engine/`).
- `/edit-seller <name>`, `/edit-buyer <name>` — edit buyer/seller (and their
  organization's) profile fields. Writes to DEV Attio first, then Postgres —
  see `app/modules/ddl_commands/README.md` for the full flow and why.
  `/remove-seller`/`/remove-buyer` don't exist (see that README's "History").
- `/add-seller <org name>`, `/add-buyer <org name>` — create a new
  seller/buyer role, searching for an existing organization first (attach
  to it) and creating a brand new one only if nothing matched. Same
  Attio-first principle as the edit commands, extended to creates.

`matching_engine` and `ddl_commands` are two modules under `app/modules/`
for functional modularity only — they are **not** separately deployed. The
root `main.py` is the one real entrypoint: it builds a single Slack
`AsyncApp`, registers both modules' command/action/view handlers against
it, and serves one `POST /slack/events`. Each module also has its own
`bootstrap.py::create_app()` for running that module standalone (its own
test suite / isolated dev) — neither is what actually gets deployed.

## Why one process, not two

Slack ties one bot identity to one Slack App — one bot token, one signing
secret, and critically, **one Interactivity & Shortcuts Request URL for the
whole app** (not per-command). Almost everything past the initial slash
command — every modal, every button — is interactivity. Two independently
deployed services can't both be "the" interactivity target of one Slack app
without something routing between them, so this bot runs as one process.

Each module keeps its own independent SQLAlchemy repositories reading the
same shared `app.models` package — see `/modular-monolith`'s module
boundaries for how cross-module access is governed (`app.modules.organizations`
for the shared `Organization` entity, `app.modules.attio` for the vendor
integration, `app.modules.notifications`/`app.modules.utilities` for
cross-cutting infra).

## Setup

```bash
uv sync
cp .env.example .env  # then fill in real values — one shared Slack token/secret for both modules
```

## Running

```bash
RELOAD=true uv run python main.py
```

or via Docker Compose (builds one image from the root `Dockerfile`, plus a
throwaway local Postgres and a one-shot migration step —
`COMPOSE_DB_PORT`/`COMPOSE_BOT_PORT` override the default host ports if
`55433`/`8080` collide with something else already running):

```bash
docker compose up --build
```

- `GET /health` — liveness, no database dependency.
- `GET /readiness` (alias `GET /ready`) — confirms database connectivity.
- `POST /slack/events` — the one Slack callback endpoint for all 5 commands.
  Signature-verified by Bolt.

### Configuring the Slack app

One Slack app for all 5 commands — see `docs/dev/SLACK_APP_SETUP.md` at the
repo root for the full checklist (Slash Commands table, Interactivity URL,
OAuth scopes, signing secret). `ddl_commands` also needs `ATTIO_API_KEY`/
`ATTIO_WEBHOOK_SECRET` (DEV Attio write access + webhook signing) alongside
the shared Slack credentials.

## Testing

```bash
uv run pytest
```

Runs this root's own merged-dispatch suite
(`tests/integration/test_merged_command_dispatch.py` — proves both modules'
handlers route correctly through the one shared Slack app) plus every
module's own business-logic/wiring suite under `app/modules/*/tests/`, plus
`tests/test_architecture.py` (cross-module layering fitness tests) and
`tests/test_env_example.py` (`.env.example` stays in sync with every
module's `Settings`).

## Layout

```
server/
├── main.py              # the real entrypoint — builds the one AsyncApp
├── pyproject.toml        # single uv project — no workspace, no path dependencies
├── Dockerfile             # the one deployed image
├── docker-compose.yml     # local dev: this bot + Postgres + one-shot migration
├── alembic/, alembic.ini  # schema migrations, owned by this repo
├── app/
│   ├── models/            # SQLAlchemy models shared across modules
│   └── modules/
│       ├── matching_engine/   # /find-match
│       ├── ddl_commands/        # /edit-seller, /edit-buyer, /add-seller, /add-buyer
│       ├── organizations/         # shared Organization persistence
│       ├── attio/                   # Attio vendor integration
│       ├── notifications/             # cross-module Slack notifier Port
│       └── utilities/                   # cross-cutting infra (logging, retry, Money, DB wiring)
└── tests/                 # merged-app dispatch + cross-module architecture tests
```

See `SCHEMA.md` (this directory) for the Postgres schema reference, and
each module's own `README.md` for module-specific detail.
