# mcp

The Wusool MCP (v1): advisors find, add, edit and bulk-import buyers and sellers
from Claude, under their own Slack sign-in, with the same duplicate checks as
Slack. It is served from the Toolkit app at `/mcp` (Streamable HTTP, stateless).

## Tools

| Tool | Does | Saves |
| -- | -- | -- |
| `find_buyers`, `find_sellers` | Look up by company name or exact domain | Read only |
| `add_buyer`, `add_seller` | Add the record, and its company if new. A company already holding the role comes back as `existing` | Straight away (Attio, then Postgres) |
| `edit_buyer`, `edit_seller` | Change only the fields sent | Straight away |
| `bulk_import_buyers`, `bulk_import_sellers` | Check up to 1,000 rows: new, existing, invalid | Nothing |
| `confirm_import` | After the person says go, adds the new rows in the background | The rows |
| `get_import` | Progress: added, skipped, failed | Read only |

No tool deletes, sends anything, spends provider credits or shows fees.

The tools call only `ddl_commands`' public functions (`add_one`, `edit_one`,
`find_records`, `preview_*`, `commit`, `status`). A field map follows the
bulk-upload row rules, and the field list in each tool description comes from
the same `FieldSpec`s the Slack forms use, so it can't drift.

**The contract only grows.** Claude conversations and skills depend on tool and
field names: add, never rename or change a meaning. A breaking change is a new tool.

## Structure

```
mcp/
  config.py          # McpSettings: MCP_PUBLIC_URL, MCP_TOKEN_SECRET, MCP_CALLS_PER_HOUR
  bootstrap.py       # composition root: wires adapters into the server; routes for main.py
  domain/            # signing.py (HMAC with a purpose), access.py (Caller, Permission, scope)
  application/       # ports/stores.py: PermissionChecker, IdempotencyStore
  persistence/       # adapters.py: allow-all permissions, in-memory idempotency
  api/
    oauth.py         # the OAuth 2.1 authorization server and the Slack callback
    tokens.py        # what each signed client id, code and token carries
    runner.py        # the one wrapper every tool call goes through
    tools/           # records.py (find/add/edit), imports.py (bulk), schemas.py (contract)
```

A new tool is its models in `tools/schemas.py` plus a thin function calling
`runner.run(name, permission, call, output=..., request_id=...)`. The runner
handles the caller, the permission check, `request_id` replay, the per-person
rate limit, one log line (`mcp_tool_call tool=… user=… duration_ms=… result=…`,
never record contents) and turning errors into sentences.

## Sign-in

The MCP authorization spec: OAuth 2.1 with PKCE (S256), dynamic client
registration, and authorization-server and protected-resource metadata.

1. Claude registers at `/register`. Only Claude's connector callback and
   localhost (MCP Inspector) are accepted as redirects. The client id is a
   signed record of the client, and its secret is derived from the id.
2. `/authorize` sends the person to Sign in with Slack (the `auth` module) with
   a signed state. Slack returns them to `/mcp/oauth/callback`.
3. The callback lets in only the bot's workspace, and only active members who
   aren't guests. It redirects to Claude with a signed code (60 seconds, single use).
4. `/token` gives an access token (1 hour, scope `crm`, valid only at `/mcp`) and
   a refresh token (30 days). Every refresh asks Slack again: someone who left is
   refused within the hour. If Slack can't be reached, the refresh goes through
   and is logged, so an outage doesn't sign everyone out.

Nothing is stored. Each artifact is HMAC-signed with `MCP_TOKEN_SECRET` and its
own purpose, so a refresh token never passes as an access token. A deploy signs
no one out; rotating the secret signs everyone out. A single refresh token can't
be revoked, so `/revoke` isn't offered.

## In memory for now

Idempotency results (24 hours), used codes and rate limits live in process.
That is correct for one server per environment (the toolkit runs as a single
instance) and is lost on a restart. Phase 0 adds Postgres adapters behind the
same ports, and real roles behind `PermissionChecker` (in v1 every active member
passes). Later areas add their own token scope rather than widening `crm`.

## Setup

- `MCP_PUBLIC_URL`: the Toolkit's public base URL. `MCP_TOKEN_SECRET`: a long
  random string, in Secrets Manager.
- Sign in with Slack must be set up (`SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`),
  and the Slack app must list `<MCP_PUBLIC_URL>/mcp/oauth/callback` as a
  redirect URL.
- Until all of these are set, `/mcp` isn't mounted.

Note: this package is `app.modules.mcp`, and the SDK is the top-level `mcp`. The
tests folder has no `__init__.py`, so pytest never puts `app/modules` on
`sys.path`, where `mcp` would resolve to this package.
