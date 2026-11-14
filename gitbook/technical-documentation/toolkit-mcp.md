# Wusool MCP

## What it does

The Wusool MCP lets advisors find, add, edit and bulk-import buyers and sellers from Claude, signed in with their own Slack account. It runs inside the Toolkit server at `/mcp` (Streamable HTTP, stateless) in the `mcp` module. It adds no tables.

## Tools

| Tool | Does | Saves |
| --- | --- | --- |
| `find_buyers`, `find_sellers` | Look up by company name or exact domain | Read only |
| `add_buyer`, `add_seller` | Add the record, and its company if new. A company that already holds the role comes back as `existing` | Straight away |
| `edit_buyer`, `edit_seller` | Change only the fields sent | Straight away |
| `bulk_import_buyers`, `bulk_import_sellers` | Check up to 1,000 rows. Returns new, existing and invalid rows | Nothing |
| `confirm_import` | After the person agrees, adds the new rows in the background | The rows |
| `get_import` | Progress: added, skipped, failed | Read only |

No tool deletes, sends, spends provider credits or shows fees. Tool and field names only grow: a breaking change becomes a new tool, because conversations and skills depend on them.

## How a call runs

- The tools call `ddl_commands`' public functions: `add_one`, `edit_one`, `find_records`, `preview_buyers`, `preview_sellers`, `commit` and `status`. Writes go to Attio first, then the database, as in [Profile commands](toolkit-profile-commands.md) and [Bulk upload](toolkit-bulk-upload.md).
- A single add follows the bulk-upload row rules: `org_name`, `domain`, `target_vertical` for buyers, and optional `fields` keyed like the template columns. Each tool description lists the keys and allowed values, built from the same field definitions as the Slack forms.
- Every add, edit and confirm carries a `request_id`. A retry with the same id returns the first result and never writes twice.
- One wrapper handles every call: the signed-in person, the permission the tool declares, the `request_id`, a per-person hourly limit (`MCP_CALLS_PER_HOUR`), one log line per call (tool, Slack user, duration, result, never record contents) and plain-language errors. A crash returns a generic error, never a stack trace.
- Every write leaves a `command_runs` row and an activity with source `mcp`, attributed to the person's Slack user.

## Sign-in

The server follows the MCP authorization spec: OAuth 2.1 with PKCE (S256), dynamic client registration, and authorization-server and protected-resource metadata.

1. Claude registers at `/register`. Only Claude's connector callback and localhost redirects are accepted.
2. `/authorize` sends the person to Sign in with Slack (the shared `auth` module). Slack returns them to `/mcp/oauth/callback`.
3. Only the bot's workspace is let in, and only active members who are not guests.
4. `/token` issues an access token (1 hour, scope `crm`, valid only for `/mcp`) and a refresh token (30 days). Every refresh asks Slack again, so someone who left is refused within the hour. If Slack can't be reached, the refresh is allowed and logged.

Client ids, codes and tokens are HMAC-signed with `MCP_TOKEN_SECRET`, each for its own purpose, so nothing is stored. Codes are single use. A deploy signs no one out. Rotating the secret signs everyone out. One refresh token can't be revoked on its own, so `/revoke` isn't offered.

## Setup

- `MCP_PUBLIC_URL`: the Toolkit's public base URL.
- `MCP_TOKEN_SECRET`: a long random value in the toolkit secret.
- Sign in with Slack must be configured (`SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`), and the Slack app must list `<MCP_PUBLIC_URL>/mcp/oauth/callback` as a redirect URL.
- A Claude organization owner adds the connector with the URL `<MCP_PUBLIC_URL>/mcp`.

Until the settings are present, `/mcp` isn't mounted.

## Limits

- Stored results for `request_id`, used codes and rate limits are kept in memory. That is correct for the single Toolkit instance, and a restart clears them. Phase 0 moves them to Postgres behind the same interfaces.
- Every active member passes the permission check in v1. Each tool already declares the permission it needs (`buyers.read`, `buyers.write`, `sellers.read`, `sellers.write`, `imports.write`), so phase 0 can add roles without changing tools.
- The company name, domain and a buyer's `target_vertical` can't be edited.
