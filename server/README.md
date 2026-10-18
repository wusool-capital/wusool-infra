# Wusool Toolkit Bot

One Slack bot, one process, one token — five commands:

- `/find-match <buyer name>` — the buyer-seller matching workflow
  (`app/modules/matching_engine/`).
- `/edit-seller <name>`, `/edit-buyer <name>` — edit buyer/seller (and their
  organization's) profile fields. Writes to SOURCE Attio first, then Postgres —
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

Secrets are not kept in a `.env` file. Every module's `Settings` reads the
toolkit secret from AWS Secrets Manager at startup (`/wusool/dev/toolkit`
locally, `/wusool/<env>/toolkit` deployed) through boto3's default credential
chain: your AWS profile locally, the instance role on EC2. The same code path
runs everywhere.

One-time, add the profile to `~/.aws/config` (latest AWS CLI v2: older versions
ignore the 7-day session; see `docs/internal/dev/AWS_ACCESS.md`):

```ini
[sso-session wusool]
sso_start_url = https://d-9967b18774.awsapps.com/start
sso_region = eu-central-1
sso_registration_scopes = sso:account:access

[profile wusool-sso]
sso_session = wusool
sso_account_id = 030179310793
sso_role_name = WusoolDeveloper
region = eu-central-1
```

Then, each week (the Identity Center session lasts 7 days):

```bash
export AWS_PROFILE=wusool-sso
aws sso login
uv sync
uv run python main.py
```

Until your Identity Center user exists, `aws login --profile wusool` with your
IAM user works for `uv run` (the dev dependencies include the `botocore[crt]`
that boto3 needs for it). Docker Compose cannot use `aws login` credentials,
so it needs the SSO profile.

- Secrets are read once at startup. A secret edit applies on the next restart
  (including uvicorn auto-reload), not to a running process. An expired AWS
  session blocks only starting the app, not a running one.
- A local `.env` still outranks the secret, so delete any old `server/.env`
  that holds secrets. Use `.env` or exported variables only for non-secret
  overrides such as `LOG_LEVEL` or `ATTIO_IS_TEST`. `.env.example` lists them.
- Tests and `./checks.sh` set `AWS_SECRETS_MANAGER_SECRET_ID=""`, so they never
  call AWS.
- Devs can read the dev secret only; the prod secret is denied.
- The database login in the secret (`wusool_app`) can read and change data but
  not the schema: DDL, `TRUNCATE` and edits to `alembic_version` fail. Migrations
  run only in the deploy pipeline. For schema work, test with `docker compose up`.
  See `docs/internal/dev/DB_ROLES.md`.

### Overriding a value for yourself

A value from the secret loses to anything you set locally. Precedence, highest
first: explicit arguments, your shell environment, `server/.env`, the dev secret.

- **One run:** `ATTIO_IS_TEST=true uv run python main.py`, or `export KEY=value`
  for the whole shell. `unset KEY` removes it; an empty `KEY=` blanks the value.
- **Every run:** put `KEY=value` in `server/.env`. It is gitignored.
- **Docker Compose:** Compose only passes the variables listed in
  `docker-compose.yml`. Add others under `environment:` in a
  `server/docker-compose.override.yml`, which is gitignored.
- **Names:** the setting name in upper case, with its prefix. For example
  `ATTIO_API_KEY` and `ATTIO_IS_TEST`; `.env.example` lists them.

This changes only your machine. To change a value for everyone, edit the secret.

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

Compose mounts `~/.aws` into the container and passes `AWS_PROFILE` (default
`wusool-sso`, so name your profile that), so run `aws sso login` first. The bundled Postgres overrides
`DATABASE_URL`; every other secret still comes from the dev secret.

- `GET /health` — liveness, no database dependency.
- `GET /readiness` (alias `GET /ready`) — confirms database connectivity.
- `POST /slack/events` — the one Slack callback endpoint for all 5 commands.
  Signature-verified by Bolt.
- `/desktop/*` — the `meetings` module's REST surface for the WusoolScribe
  desktop app (transcript ingestion, summarization, status polling), a
  separate Bearer-token-authenticated surface with no Slack command of its
  own. See `app/modules/meetings/README.md`.

### Configuring the Slack app

One Slack app for all 5 commands — see `docs/internal/dev/SLACK_APP_SETUP.md` at the
repo root for the full checklist (Slash Commands table, Interactivity URL,
OAuth scopes, signing secret). `ddl_commands` also needs `ATTIO_API_KEY`/
`ATTIO_WEBHOOK_SECRET` (SOURCE Attio write access + webhook signing) alongside
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
│       ├── discrepancies/       # /check-buyer
│       ├── ddl_commands/        # /edit-seller, /edit-buyer, /add-seller, /add-buyer
│       ├── meetings/              # /desktop/* — desktop-app transcript summarization
│       ├── organizations/           # shared Organization persistence
│       ├── attio/                     # Attio vendor integration
│       ├── notifications/               # cross-module Slack notifier Port
│       └── utilities/                     # cross-cutting infra (logging, retry, Money, DB wiring)
└── tests/                 # merged-app dispatch + cross-module architecture tests
```

See `SCHEMA.md` (this directory) for the Postgres schema reference, and
each module's own `README.md` for module-specific detail.
