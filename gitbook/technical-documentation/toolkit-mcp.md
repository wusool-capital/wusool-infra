# Wusool MCP

## What it does

The Wusool MCP lets advisors find, add, edit and bulk-import buyers and sellers from Claude, signed in with their own Slack account. It also lets them read and edit the GCC SME Benchmark's peer dataset. It runs inside the Toolkit server at `/mcp` (Streamable HTTP, stateless) in the `mcp` module. It has no tables of its own. The benchmark tables belong to the `benchmark_data` module. Every tool call is recorded in `activities`.

## Tools

| Tool | Does | Saves |
| --- | --- | --- |
| `find_buyers`, `find_sellers` | Look up by company name or exact domain | Read only |
| `add_buyer`, `add_seller` | Add the record, and its company if new. A company that already holds the role comes back as `existing` | Straight away |
| `edit_buyer`, `edit_seller` | Change only the fields sent; null empties a field | Straight away |
| `bulk_import_buyers`, `bulk_import_sellers` | Check up to 1,000 rows. Returns new, existing and invalid rows | Nothing |
| `confirm_import` | After the person agrees, adds the new rows in the background | The rows |
| `get_import` | Progress: added, skipped, failed | Read only |
| `get_buyer`, `get_seller` | An advisor template of up to 100 records in one call, keyed like the edit tools' `fields`. `fields` picks exact columns and `return_all` gives every column for up to 25 ids. Ids that are unknown, inactive or of the other kind come back in `not_found` | Read only |
| `list_buyers`, `list_sellers` | Active records matching `filters` on any field (`{field, op, value}`), up to 50 a page. When `truncated`, pass `next_offset` as `offset`. Rows hold ids only, so pass them to `get_*` for numbers | Read only |
| `check_buyer` | The `/check-buyer` check: missing or conflicting matching criteria | Read only |
| `list_field_options` | Every field's type, how to send a value, allowed values, whether it is editable and the filter operators it takes. `fields` returns just those keys | Read only |

No tool deletes, sends, spends provider credits or shows fees.

The five benchmark tools, which edit the public benchmark's peer dataset, are described in [Benchmark tools](toolkit-mcp-benchmark.md).

Tool and field names only grow. A breaking change becomes a new tool, because conversations and skills depend on them.

## How a call runs

- The tools call `ddl_commands`' public functions: `add_one`, `edit_one`, `find_records`, `preview_buyers`, `preview_sellers`, `commit` and `status`. Writes go to Attio first, then the database, as in [Profile commands](toolkit-profile-commands.md) and [Bulk upload](toolkit-bulk-upload.md).
- A single add follows the bulk-upload row rules: `org_name`, `domain`, `target_vertical` for buyers, and optional `fields` keyed like the template columns. Each add, edit and bulk-import description says which keys are required. It then lists the optional keys with their types and allowed values, built from the same field definitions as the Slack forms. Long value lists point to `list_field_options`.
- Values in `fields` arrive as JSON text. They are converted the way file uploads convert them: dates, amounts, numbers, yes/no, and lists for multi-selects. A value that can't convert is refused with what the field takes.
- Every add, edit and confirm carries a `request_id`. A retry with the same id returns the first result and never writes twice. The same id with different arguments is refused.
- A bulk preview belongs to the person who made it. Only they can confirm it or read its progress.
- Edits apply only to active records. An inactive duplicate is treated as not found.
- One wrapper handles every call. It finds the signed-in person, checks the permission the tool declares, replays a repeated `request_id`, and applies a per-person hourly limit (`MCP_CALLS_PER_HOUR`). It writes one log line per call (tool, Slack user, duration, result, never record contents) and turns errors into plain sentences. A crash returns a generic error, never a stack trace.
- Every write leaves a `command_runs` row and an activity with source `mcp`, attributed to the person's Slack user.
- Every tool call, read or write, also leaves one `mcp.tool_called` activity. It holds the person's Slack user, the tool, how it ended (`ok`, `replayed`, `refused`, `rate_limited`, `error` and so on) and the duration. It never holds arguments or records. A failure to write it is logged and never fails the tool.

## Lists and checks

- `list_buyers` and `list_sellers` take one `filters` list of `{field, op, value}` on any column. With no filters, every active record is listed. The fields, operators and rules are in [Record filters](toolkit-record-filters.md).
- `get_buyer` and `get_seller` return an advisor template by default. Their `fields` option reads exact columns, `return_all` reads every column, and `list_field_options` lists them all.
- Records removed in Attio are left out of lists, and `get_*` treats them as not found.
- Results are ordered by company name. A list returns up to 50 records a page and gives `next_offset` when more match.
- `check_buyer` runs without an advisor's note, so it never calls the model. It reports what the profile is missing or holds in conflict.
- Tool descriptions list option values only for short lists. Longer ones, such as verticals and countries, come from `list_field_options`.

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
- A Claude organization owner adds the connector with the URL `<MCP_PUBLIC_URL>/mcp`. In production that is `https://toolkit-3-69-122-231.sslip.io/mcp`. The steps are in [Wusool MCP](../user-guide/toolkit-claude.md).

Until the settings are present, `/mcp` isn't mounted.

## Limits

- Stored results for `request_id`, used codes and rate limits are kept in memory. That is correct for the single Toolkit instance, and a restart clears them. Phase 0 moves them to Postgres behind the same interfaces.
- Every active member passes the permission check in v1. Each tool already declares the permission it needs (`buyers.read`, `buyers.write`, `sellers.read`, `sellers.write`, `imports.write`, `benchmark.read`, `benchmark.write`), so phase 0 can add roles without changing tools.
- The company name, domain and a buyer's `target_vertical` can't be edited.
