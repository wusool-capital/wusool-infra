# Wusool MCP

## What it does

The Wusool MCP lets advisors find, add, edit and bulk-import buyers and sellers from Claude, signed in with their own Slack account. It also lets them read and edit the GCC SME Benchmark's peer dataset. It runs inside the Toolkit server at `/mcp` (Streamable HTTP, stateless) in the `mcp` module. It has no tables of its own. The benchmark tables belong to the `benchmark_data` module. Every tool call is recorded in `activities`.

## Tools

| Tool | Does | Saves |
| --- | --- | --- |
| `find_buyers`, `find_sellers` | Look up by company name or exact domain | Read only |
| `add_buyer`, `add_seller` | Add the record, and its company if new. A company that already holds the role comes back as `existing` | Straight away |
| `edit_buyer`, `edit_seller` | Change only the fields sent | Straight away |
| `bulk_import_buyers`, `bulk_import_sellers` | Check up to 1,000 rows. Returns new, existing and invalid rows | Nothing |
| `confirm_import` | After the person agrees, adds the new rows in the background | The rows |
| `get_import` | Progress: added, skipped, failed | Read only |
| `get_buyer`, `get_seller` | Every field of one record, keyed like the edit tools' `fields` | Read only |
| `list_buyers`, `list_sellers` | Active records matching filters, up to 50, with `truncated` when more match | Read only |
| `check_buyer` | The `/check-buyer` check: missing or conflicting matching criteria | Read only |
| `list_field_options` | Every field's type and allowed values | Read only |
| `get_benchmark_overview` | Revenue bands, metric weights, and every peer set with its sample size. Every row shows who last changed it and when | Read only |
| `get_peer_cut` | One peer set with its percentile anchors, and who last changed it | Read only |
| `edit_benchmark_peer_cut` | Change a peer set's sample size, flags or anchors. Only the fields sent change | Straight away |
| `edit_revenue_band` | Change a revenue band's label, ceiling or adjustment factors | Straight away |
| `set_metric_weights` | Set every metric's weight for a mode. They must add up to 100 | Straight away |

No tool deletes, sends, spends provider credits or shows fees.

The benchmark tools change what visitors to the public benchmark are scored against, as soon as they are saved. Each edit is checked first. Anchors must rise from p10 to p90. Band ceilings must keep rising, and only the top band is open-ended. Weights must add up to 100. A refused edit saves nothing.

For anchors, a call sends either a metric's five numbers or only the percentiles to change, such as `{"p50": 67}`. The rest keep their value, and the merged result must still rise from p10 to p90.

Each changed row stores the editor's name and the time. Old values are not kept yet, so Claude reads a row first and tells the person what it held and who last changed it. The tools' own descriptions say so.

Tool and field names only grow. A breaking change becomes a new tool, because conversations and skills depend on them.

## How a call runs

- The tools call `ddl_commands`' public functions: `add_one`, `edit_one`, `find_records`, `preview_buyers`, `preview_sellers`, `commit` and `status`. Writes go to Attio first, then the database, as in [Profile commands](toolkit-profile-commands.md) and [Bulk upload](toolkit-bulk-upload.md).
- A single add follows the bulk-upload row rules: `org_name`, `domain`, `target_vertical` for buyers, and optional `fields` keyed like the template columns. Each add, edit and bulk-import description says which keys are required. It then lists the optional keys with their types and allowed values, built from the same field definitions as the Slack forms. Long value lists point to `list_field_options`. The benchmark edit descriptions list the valid metric keys for each mode.
- Every add, edit and confirm carries a `request_id`. A retry with the same id returns the first result and never writes twice. The same id with different arguments is refused.
- A bulk preview belongs to the person who made it. Only they can confirm it or read its progress.
- Edits apply only to active records. An inactive duplicate is treated as not found.
- One wrapper handles every call. It finds the signed-in person, checks the permission the tool declares, replays a repeated `request_id`, and applies a per-person hourly limit (`MCP_CALLS_PER_HOUR`). It writes one log line per call (tool, Slack user, duration, result, never record contents) and turns errors into plain sentences. A crash returns a generic error, never a stack trace.
- Every write leaves a `command_runs` row and an activity with source `mcp`, attributed to the person's Slack user.
- Every tool call, read or write, also leaves one `mcp.tool_called` activity. It holds the person's Slack user, the tool, how it ended (`ok`, `replayed`, `refused`, `rate_limited`, `error` and so on) and the duration. It never holds arguments or records. A failure to write it is logged and never fails the tool.
- A benchmark edit leaves one `benchmark.peer_cut_edited` or `benchmark.rule_edited` activity per changed row, naming the fields that changed.

## Lists and checks

- Buyer filters: `target_vertical`, `mandate_status`, `model`, `target_region`, `target_country`, `check_size_usd` and `hq_country`. Seller filters: `sector`, `hq_country`, `region`, `relationship_status` and `outreach_tier`.
- Every filter given must match. Region and country lists match when any value overlaps. A company with several HQ countries or regions matches any one of them. A value outside a field's options is refused with the allowed values.
- `check_size_usd` keeps buyers whose check size range contains it. A buyer with no minimum or maximum set still matches.
- Records removed in Attio are left out of lists, and `get_*` treats them as not found.
- Results are ordered by company name. A list returns at most 50 records and says when more match.
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
- A Claude organization owner adds the connector with the URL `<MCP_PUBLIC_URL>/mcp`.

Until the settings are present, `/mcp` isn't mounted.

## Limits

- Stored results for `request_id`, used codes and rate limits are kept in memory. That is correct for the single Toolkit instance, and a restart clears them. Phase 0 moves them to Postgres behind the same interfaces.
- Every active member passes the permission check in v1. Each tool already declares the permission it needs (`buyers.read`, `buyers.write`, `sellers.read`, `sellers.write`, `imports.write`, `benchmark.read`, `benchmark.write`), so phase 0 can add roles without changing tools.
- The company name, domain and a buyer's `target_vertical` can't be edited.
- The benchmark tools use the same `crm` token scope as the CRM tools, so one connection covers both. Adding or removing sectors and stages isn't offered.
