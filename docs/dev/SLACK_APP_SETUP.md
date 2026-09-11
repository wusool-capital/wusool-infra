# Slack App Setup: Wusool Toolkit Bot

Manual, one-time setup at [api.slack.com/apps](https://api.slack.com/apps) for
**one** Slack bot serving all 9 commands — `/find-match` (matching-engine),
`/enrich-seller`, `/enrich-buyer` (enrichment), `/edit-seller`,
`/edit-buyer`, `/add-seller`, `/add-buyer` (ddl-commands), and `/help`/
`/toolkit-status` (answered directly in `server/main.py` — neither is owned
by any one module). There is no bare `/enrich` — every enrichment command
is kind-scoped on purpose, see below.
`matching_engine`, `enrichment`, `discovery`, and
`ddl_commands` are separate modules under `server/app/modules/` for
functional modularity, but they are **one process, one Slack app, one
token** — see `server/README.md` for why (Slack ties one Interactivity
Request URL to one app; two separately-deployed services can't both be it).
`discovery` has no slash command of its own — it's reached only through a
button on `/find-match`'s result message.

`/remove-seller`/`/remove-buyer` don't exist — see
`server/app/modules/ddl_commands/README.md` ("History") for why.

If `/find-match` already has a Slack app registered from before this bot
existed, **reuse that app** — just add the new Slash Commands to it below.
Don't create a second app.

## 1. Create the app (skip if `/find-match`'s app already exists)

New app at api.slack.com/apps → **From scratch** → name it (e.g.
`Wusool Toolkit Bot`) → pick the workspace.

## 2. Slash Commands

**Features → Slash Commands → Create New Command**, one per row (all 9
point at the same URL — Bolt routes internally by command name):

| Command | Request URL | Short Description | Usage Hint |
|---|---|---|---|
| `/find-match` | `https://<bot-host>/slack/events` | Find and score buyer-seller matches | `<buyer org name>` |
| `/enrich-seller` | `https://<bot-host>/slack/events` | Research and fill missing seller fields | `<seller org name>` |
| `/enrich-buyer` | `https://<bot-host>/slack/events` | Research and fill missing buyer fields | `<buyer org name>` |
| `/edit-seller` | `https://<bot-host>/slack/events` | Edit a seller profile | `<seller org name>` |
| `/edit-buyer` | `https://<bot-host>/slack/events` | Edit a buyer profile | `<buyer org name>` |
| `/add-seller` | `https://<bot-host>/slack/events` | Add a new seller | `<organization name>` |
| `/add-buyer` | `https://<bot-host>/slack/events` | Add a new buyer | `<organization name>` |
| `/toolkit-status` | `https://<bot-host>/slack/events` | Show uptime, database, and Attio mode | *(none)* |
| `/help` | `https://<bot-host>/slack/events` | List every command and how to use it | *(none)* |

`/status` is a Slack-reserved word and cannot be registered — `/toolkit-status`
is the actual command name.

`/help`/`/toolkit-status` are answered directly in `server/main.py`
(`_COMMAND_HELP`, `_register_status_command`) — neither is owned by any
one module, so keep `_COMMAND_HELP` in sync with this table when a
command is added, removed, or renamed.

There is no bare `/enrich` — every enrichment command is kind-scoped, so
an org with both an active buyer and seller role never needs a
role-selection modal just to pick which kind you meant. If a name still
matches more than one *organization* within that kind, a modal disambiguates
among those.

> **`<bot-host>` isn't provisioned yet.** The toolkit stack's `apps` list has
> one entry for the `server/` image — but
> whether that module has ever actually been `apply`'d to a live instance
> hasn't been confirmed from this environment (no AWS credentials
> available here). Confirm that before relying on any real hostname, or
> use `ngrok` against a local `RELOAD=true uv run python server/main.py` for testing.

## 3. Interactivity & Shortcuts

**Features → Interactivity & Shortcuts** → toggle on → **Request URL**: same
`https://<bot-host>/slack/events`.

This is the one URL for the whole app — every modal submission and button
click from the 7 interactive commands routes through it (`/edit-seller`/
`/edit-buyer` are a 3-step modal flow: disambiguation → field picker →
edit form; `/add-seller`/`/add-buyer` are a 2- or 3-step flow:
organization selection (skipped if the search found nothing) → add form;
`/enrich-seller`/`/enrich-buyer` post a research proposal as a message
with a single "Review & Save" button, not a modal, since research + LLM
extraction routinely runs past Slack's 3-second modal-open budget).
`/help`/`/toolkit-status` have no modal or button of their own — they
still go through this same URL as every slash command does, they just
never trigger a follow-up interaction. This is exactly why every one of
these modules had to become one process: Slack has no per-command
interactivity URL.

## 4. OAuth & Permissions

**Features → OAuth & Permissions → Bot Token Scopes**, add:

- `commands` — receive all 9 slash commands.
- `chat:write` — `chat.postEphemeral` (usage messages, confirmation
  prompts, error messages) and the `response_url` webhook used to replace
  messages after button clicks.

**Install App to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
into `SLACK_BOT_TOKEN` (one shared value, `server/.env`).

## 5. Signing secret

**Settings → Basic Information → App Credentials** → copy **Signing Secret**
into `SLACK_SIGNING_SECRET`. Bolt verifies every request against this
(`v0:<timestamp>:<body>` HMAC-SHA256) — get it wrong and every command
silently 401s.

## 6. Attio write access (for `/edit-*`/`/add-*` only)

`/edit-seller`/`/edit-buyer`/`/add-seller`/`/add-buyer` write to SOURCE Attio
before writing to Postgres — see
`server/app/modules/ddl_commands/README.md` ("Why Attio-first") for
the full reasoning. Set `ATTIO_API_KEY` to a write-capable SOURCE workspace
key (the same workspace `crm-sync`'s PowerShell scripts use via
`SOURCE_ATTIO_API_KEY`). `/find-match` needs none of this.

One SOURCE workspace serves both environments, so also set `ATTIO_IS_TEST`:
`true` for anything that is not production. It defaults to `true`, and the
deployed environments get it from Terraform — but a local `.env` that sets a
real key and forgets this flag would write test records indistinguishable
from real CRM data, so set it explicitly. There is one SOURCE key across both
environments — `ATTIO_IS_TEST` is the only thing separating them.

## Before enabling for real users

1. **Confirm the bot is actually deployed and reachable** — Terraform's
   `app_subdir` builds from the toolkit root (both folders, one image)
   rather than `matching-engine/` alone; a fresh `tofu plan`/`apply`
   (reviewed by a second person) is needed to pick that up if this module
   has been applied before, or a first `apply` if it hasn't.
2. **First real invocation of each command is the first real test against
   prod Attio + Postgres** — no canary org, no dry-run mode. This matters
   most for `/add-seller`/`/add-buyer`: their Attio *create* calls
   (`POST .../records`, `POST .../entries`) have never been exercised
   against live Attio by this bot, only matched against the exact shapes
   `crm-sync`'s own PowerShell scripts already use live. Whoever runs any
   of these commands first should watch Slack, and check both the Attio
   record and the Postgres row afterward, on a real but low-stakes org.

## Reference

Full design rationale (the edit flow, why Attio-first, which fields are
excluded and why) is in `server/README.md` and
`server/app/modules/ddl_commands/README.md`.
