# Interactions engine

The interactions engine reads the team's Gmail and Google Calendar and records who wrote to whom, and when. Its goal is to keep Attio's last interaction and connection strength live on Organizations and Person.

Today it only reads and stores. It doesn't write to Attio yet.

## Status

| Stage | State |
| --- | --- |
| Read Gmail and Calendar metadata into PostgreSQL | Built, off by default |
| Match each address to a Person and an Organization | Built |
| Interaction dates and connection strength | Built as code, not yet run on live data |
| Shadow week: compare with Attio's own labels | Not started |
| Write the fields to Attio | Not started |
| Create contacts from email, roll up to Deals, retire Companies and People | Not started |

## What it reads

- **Gmail:** sender, recipients, subject, Message-ID, labels, and time. It never requests message bodies or attachments.
- **Calendar:** title, start time, organizer, and each guest's response.
- **Mailboxes:** the addresses in `INTERACTIONS_MAILBOXES`. That is Jules and Ramzy today. Hugo's is added once his primary address is confirmed. The `tech@` inbox is excluded.
- **Team domains:** `wusoolcapital.com` and `dopaminecap.com` count as one team.

It ignores internal-only mail and meetings, spam, trash, drafts, and chat. It also ignores all-day and cancelled events, meetings the team member declined, calendar notification emails, and auto-replies.

## How a pass works

1. The first time, it records Gmail's change bookmark, then reads the last 12 months one page at a time. It saves its place after every page, so a restart resumes.
2. After that, each poll reads only the changes since the saved bookmark. Calendar works the same way with a sync token.
3. If Google drops a bookmark, Gmail re-reads from the last sync minus one day. Calendar re-reads its full window.
4. Rows and the saved position are written in one transaction. A re-read email is skipped. A re-read meeting is updated in place, and cancelled meetings are flagged.
5. Each outside address is then matched to a Person and an Organization.
6. Once a day, it deletes interactions older than 12 months.

## Linking to CRM records

A unique email address links its Person. The address's domain, or a parent domain, links its Organization. A Person's own Organization wins over the domain.

An address shared by several Persons links nothing. A domain shared by several Organizations links no Organization. Links are only filled in, never replaced. A review table for the shared cases is planned.

## Google access

One service account reads each mailbox through domain-wide delegation. A Workspace admin authorizes it for two read-only scopes: Gmail and Calendar.

The Gmail scope has to be the full read-only one, because Google's metadata-only scope can't filter mail by date. The code still requests headers only.

The key is the Secrets Manager value `GOOGLE_SERVICE_ACCOUNT_JSON`. Deleting the admin's delegation entry stops access at the next poll. Setup, rotation, and revocation are in the Google access runbook, `docs/runbooks/google-delegation.md`.

## Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `INTERACTIONS_ENABLED` | `false` | Turns the loop on. Set it in one environment only. |
| `INTERACTIONS_POLL_INTERVAL_S` | `900` | Seconds between passes. |
| `INTERACTIONS_MAILBOXES` | Jules and Ramzy | Primary addresses to read, separated by spaces. |
| `INTERACTIONS_INTERNAL_DOMAINS` | both company domains | Team domains. The first is the main one. |
| `INTERACTIONS_BACKFILL_MONTHS` | `12` | How far back the first read goes. |
| `INTERACTIONS_RETENTION_MONTHS` | `12` | How long interactions are kept. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | none | The service-account key. Secrets Manager only. |

The scoring settings, which are the points, half-life, bonus, and label cut-offs, start at the plan's values. They are tuned during the shadow week.

## Data stored

Three PostgreSQL tables hold the data: `interactions`, `interaction_participants`, and `mailbox_sync_cursors`. They hold headers, subjects, and event details, never bodies.

Subjects can contain deal names, so treat these tables like other CRM data. Nothing is sent to a third party.

## Safeguards and limits

- The loop stays off unless `INTERACTIONS_ENABLED` is true and the key is valid. A missing or malformed key is logged and never echoed.
- A database lock lets only one instance run a pass. This matters because dev and prod can share a database and a Google tenant.
- One failing mailbox is logged and doesn't stop the others.
- Gmail allows 6,000 quota units a minute per user, and each message fetch costs 20. The engine fetches at most 250 messages a minute per mailbox.
- A large backfill therefore takes hours. About 20,000 messages take about 80 minutes.
- If Google issues no Calendar sync token, each pass re-reads the last seven days instead.

## Where to look

The code is in `server/app/modules/interactions` and `server/app/modules/google_workspace`. Each has a README and a HOW-TO-READ guide. Google access is its own module so other features can reuse it.
