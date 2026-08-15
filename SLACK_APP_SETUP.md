# Slack App Setup: Wusool Toolkit Bot

Manual, one-time setup at [api.slack.com/apps](https://api.slack.com/apps) for
**one** Slack bot serving all 5 commands — `/find-match` (matching-engine)
plus `/edit-seller`, `/remove-seller`, `/edit-buyer`, `/remove-buyer`
(ddl-commands). `matching-engine/` and `ddl-commands/` are two folders in
`workflows/wusool-toolkit/` for functional modularity, but they are **one
process, one Slack app, one token** — see
`workflows/wusool-toolkit/README.md` for why (Slack ties one Interactivity
Request URL to one app; two separately-deployed services can't both be it).

`/add-seller` is intentionally excluded — blocked on an unresolved decision
about whether this bot may create new `organizations` rows.

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
| `/edit-seller` | `https://<bot-host>/slack/events` | Edit or restore a seller profile | `<seller org name>` |
| `/remove-seller` | `https://<bot-host>/slack/events` | Remove (soft-delete) a seller profile | `<seller org name>` |
| `/edit-buyer` | `https://<bot-host>/slack/events` | Edit or restore a buyer profile | `<buyer org name>` |
| `/remove-buyer` | `https://<bot-host>/slack/events` | Remove (soft-delete) a buyer profile | `<buyer org name>` |

> **`<bot-host>` isn't provisioned yet.** `terraform/environments/dev/main.tf`'s
> `apps` list has one entry, `app_subdir = "workflows/wusool-toolkit"` — but
> whether that module has ever actually been `apply`'d to a live instance
> hasn't been confirmed from this environment (no AWS credentials
> available here). Confirm that before relying on any real hostname, or
> use `ngrok` against a local `uv run uvicorn main:app` for testing.

## 3. Interactivity & Shortcuts

**Features → Interactivity & Shortcuts** → toggle on → **Request URL**: same
`https://<bot-host>/slack/events`.

This is the one URL for the whole app — every modal submission and button
click from all 5 commands routes through it. This is exactly why
`matching-engine` and `ddl-commands` had to become one process: Slack has no
per-command interactivity URL.

## 4. OAuth & Permissions

**Features → OAuth & Permissions → Bot Token Scopes**, add:

- `commands` — receive all 5 slash commands.
- `chat:write` — `chat.postEphemeral` (usage messages, confirmation
  prompts, error messages) and the `response_url` webhook used to replace
  messages after button clicks.

**Install App to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
into `SLACK_BOT_TOKEN` (one shared value, `workflows/wusool-toolkit/.env`).

## 5. Signing secret

**Settings → Basic Information → App Credentials** → copy **Signing Secret**
into `SLACK_SIGNING_SECRET`. Bolt verifies every request against this
(`v0:<timestamp>:<body>` HMAC-SHA256) — get it wrong and every command
silently 401s.

## Before enabling for real users

1. **Confirm the bot is actually deployed and reachable** — Terraform's
   `app_subdir` was recently changed to build from the toolkit root (both
   folders, one image) rather than `matching-engine/` alone; a fresh
   `tofu plan`/`apply` (reviewed by a second person) is needed to pick that
   up if this module has been applied before, or a first `apply` if it
   hasn't.
2. **Confirm the sync-guard is actually running in prod**, not just merged —
   `database/sync-postgres.ps1`'s `WHERE bot_managed_at IS NULL` guard has
   to be live in the real scheduled sync job *before* any write command
   (`/edit-seller`/`/remove-seller`/`/edit-buyer`/`/remove-buyer`) runs
   against real `wusool_crm`.
3. **First real invocation of a write command is the first real test
   against prod data** — no canary org, no dry-run mode. Whoever runs it
   first should watch Slack and spot-check the resulting row on a real but
   low-stakes org.

## Reference

Full design rationale (soft-delete, sync-guard, restore flow, why one
process) is in `workflows/wusool-toolkit/README.md` and
`workflows/wusool-toolkit/ddl-commands/README.md`.
