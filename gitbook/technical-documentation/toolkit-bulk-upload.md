# Bulk upload

## What it does

Bulk upload adds many buyers or sellers in one go. There are two ways in: a file uploaded in Slack with `/bulk-buyer` or `/bulk-seller`, and Claude through the MCP tools (planned).

Both use the same three steps in the `ddl_commands` module: preview, commit, and status. Nothing is created until the person confirms the preview.

## The Slack flow

1. `/bulk-buyer` or `/bulk-seller` opens a form with a file input. Slack can't attach a file to a slash command.
2. On submit, the bot downloads the file and checks it while a "checking" view shows.
3. If anything is wrong, the whole file is rejected and every problem is listed. Nothing is saved.
4. If the file is valid, a confirm view shows the counts. **Add** starts the work in the background.
5. When it finishes, the bot posts the result to the person in the channel.

## The file

- A CSV saved as UTF-8, or the first sheet of an `.xlsx` file. The limits are 1,000 rows and 5 MB.
- The first row holds the column labels from the template. Matching ignores case and extra spaces.
- Required columns are Organization name and Domain, plus Target vertical for buyers.
- Blank rows are skipped, and line numbers in messages are spreadsheet lines.

Cell rules follow the Slack forms:

- Lists, such as Sector focus, are separated by `;`.
- Money is a plain USD number. Dates are `YYYY-MM-DD`. Booleans are Yes or No.
- A value outside a select field's options is a problem, so nothing is dropped silently. Dropdown values match ignoring case.
- An empty cell means the field is not set.

## Two kinds of failure

A file that is not the template is rejected as a whole. That covers missing, unknown or repeated columns, an unreadable file, and too many rows. The message says "Wrong template format", gives the reason, and links the template.

A bad value in a good file is a row problem. Each one reads like `Line 7, Target vertical: not an allowed value`. The form shows the first 20. When more exist, or they are too long to fit, the full list is attached as a CSV.

## How rows are added

Rows go through the same writes as `/add-buyer` and `/add-seller`: Attio first, then the database.

- A row whose domain matches an organization that already has the role is skipped and never changes the record. The final result counts these as skipped.
- Each row is checked again just before it is added, so a rerun adds only the rows still missing.
- Added rows get a `command_runs` and activity record with the source `slack` or `mcp`.

The all-or-nothing rule applies to Claude's uploads too. A rejected list returns the exact problem on each bad row, so Claude can fix it and send it again.

## Templates

The two template files are built from the field definitions and committed in `ddl_commands/bulk_templates/`. A unit test fails when they drift. After changing a field, run `generate_bulk_templates` and commit the result.

Terraform stack `stacks/assets` uploads them to a public bucket, readable under `templates/` only. Apply it out of band, like `scribe-updates`. Then set `BULK_TEMPLATE_BASE_URL` in the toolkit secret's `env` map to the stack output `templates_base_url`.

## Slack app setup

The Slack app needs the `files:read` and `files:write` scopes and the two new commands. A workspace admin then reinstalls the app. See `docs/internal/dev/SLACK_APP_SETUP.md`.

## Limits

- Previews live in memory for an hour. A restart loses them, and the person uploads the file again.
- The checks are all-or-nothing, but the writes are not. If Attio fails halfway, rows already added stay, and the result lists the failures.
- An Excel file is read for its saved values. A formula with no saved result reads as empty. Macros and other sheets are ignored.
- A file is parsed in a background thread, and a packed workbook over 50 MB unpacked is refused.

## Code

`server/app/modules/ddl_commands`: `api/bulk_upload.py`, `api/bulk_file.py`, `api/bulk_columns.py`, and `api/slack/handlers/bulk.py`.
