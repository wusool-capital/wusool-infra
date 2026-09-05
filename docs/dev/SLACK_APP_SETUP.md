# Slack App Setup: Wusool Toolkit Bot

Manual, one-time setup at [api.slack.com/apps](https://api.slack.com/apps) for
**one** Slack bot serving all 5 commands — `/find-match` (matching-engine)
plus `/edit-seller`, `/edit-buyer`, `/add-seller`, `/add-buyer`
(ddl-commands). `matching_engine` and `ddl_commands` are two modules under
`server/app/modules/` for functional modularity, but they are **one
process, one Slack app, one token** — see
`server/README.md` for why (Slack ties one Interactivity
Request URL to one app; two separately-deployed services can't both be it).

`/remove-seller`/`/remove-buyer` don't exist — see
`server/app/modules/ddl_commands/README.md` ("History") for why.

If `/find-match` already has a Slack app registered from before this bot
existed, **reuse that app** — just add the 4 new Slash Commands to it below.
Don't create a second app.

## 1. Create the app (skip if `/find-match`'s app already exists)

New app at api.slack.com/apps → **From scratch** → name it (e.g.
`Wusool Toolkit Bot`) → pick the workspace.

## 2. Slash Commands

**Features → Slash Commands → Create New Command**, one per row (all 5
point at the same URL — Bolt routes internally by command name):

| Command | Request URL | Short Description | Usage Hint |
|---|---|---|---|
| `/find-match` | `https://<bot-host>/slack/events` | Find and score buyer-seller matches | `<buyer org name>` |
| `/edit-seller` | `https://<bot-host>/slack/events` | Edit a seller profile | `<seller org name>` |
| `/edit-buyer` | `https://<bot-host>/slack/events` | Edit a buyer profile | `<buyer org name>` |
| `/add-seller` | `https://<bot-host>/slack/events` | Add a new seller | `<organization name>` |
| `/add-buyer` | `https://<bot-host>/slack/events` | Add a new buyer | `<organization name>` |

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
click from all 5 commands routes through it (`/edit-seller`/`/edit-buyer`
are a 3-step modal flow: disambiguation → field picker → edit form;
`/add-seller`/`/add-buyer` are a 2- or 3-step flow: organization selection
(skipped if the search found nothing) → add form). This is exactly why
`matching-engine` and `ddl-commands` had to become one process: Slack has
no per-command interactivity URL.

## 4. OAuth & Permissions

**Features → OAuth & Permissions → Bot Token Scopes**, add:

- `commands` — receive all 5 slash commands.
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

`/edit-seller`/`/edit-buyer`/`/add-seller`/`/add-buyer` write to DEV Attio
before writing to Postgres — see
`server/app/modules/ddl_commands/README.md` ("Why Attio-first") for
the full reasoning. Set `ATTIO_API_KEY` to the same write-capable key
`crm-sync`'s PowerShell scripts already use (`DEV_ATTIO_API_KEY`) — not a
new credential to provision, just a second consumer of the existing one.
`/find-match` needs none of this.

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
