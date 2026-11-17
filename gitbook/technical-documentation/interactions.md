# Interactions engine

The interactions engine reads the team's Gmail and Google Calendar and records who wrote to whom, and when. Its goal is to keep Attio's last interaction and connection strength live on Organizations and Person.

It reads and stores, writes the results to Attio in production, and can create the contacts it meets.

## Status

| Stage | State |
| --- | --- |
| Read Gmail and Calendar metadata into PostgreSQL | Live on production, off by default elsewhere |
| Match each address to a Person and an Organization | Built |
| Interaction dates and connection strength | Live on production |
| Shadow week: compare with Attio's own labels | Passed on prod: 84.6% exact, 96.2% within one level |
| Write the fields to Attio | Live on production since 16 Nov |
| Create contacts from email | Live on production since 16 Nov |
| Roll up to Deals ([details](interactions-deal-rollup.md)) | Live on production since 17 Nov |
| Attio Companies and People | Left in place, no longer updated |

## What it reads

- **Gmail:** sender, recipients, subject, Message-ID, labels, and time. It never requests message bodies or attachments.
- **Calendar:** title, start time, organizer, and each guest's response.
- **Mailboxes:** the addresses in `INTERACTIONS_MAILBOXES`. That is Jules and Ramzy. Hugo's mailbox is not read, and neither is `tech@`.
- **Team domains:** `wusoolcapital.com` and `dopaminecap.com` count as one team.

It ignores internal-only mail and meetings, spam, trash, drafts, and chat. It also ignores all-day and cancelled events, meetings the team member declined, calendar notification emails, and auto-replies.

## How a pass works

1. The first time, it records Gmail's change bookmark, then reads the last 12 months one page at a time. It saves its place after every page, so a restart resumes.
2. After that, each poll reads only the changes since the saved bookmark. Calendar works the same way with a sync token.
   Calendar also reads the slice that just came inside its 180-day window, because nobody has edited those meetings.
3. If Google drops a bookmark, Gmail re-reads from the last sync minus one day. Calendar re-reads its full window.
4. Rows and the saved position are written in one transaction. A re-read email is skipped. A re-read meeting is updated in place. Cancelled, declined, and moved-away meetings are flagged so they stop counting.
5. Each outside address is then matched to a Person and an Organization.
6. Once a day, it deletes interactions older than 12 months.

## Linking to CRM records

A unique email address links its Person. The address's domain, or a parent domain, links its Organization. A Person's own Organization wins over the domain.

An address shared by several Persons links nothing. A domain shared by several Organizations links no Organization. Links are only filled in, never replaced. A review table for the shared cases is planned.

## Google access

One service account reads each mailbox through domain-wide delegation. A Workspace admin authorizes it for two read-only scopes: Gmail and Calendar.

The Gmail scope has to be the full read-only one, because Google's metadata-only scope can't filter mail by date. The code still requests headers only.

The key is the Secrets Manager value `GOOGLE_SERVICE_ACCOUNT_JSON`. Deleting the admin's delegation entry stops access at the next poll. Setup, rotation, and revocation are in the Google access runbook, `docs/runbooks/google-delegation.md`.

## Writing to Attio

The engine writes 13 fields to Organizations and Person in production, since the shadow-week gate passed. It sends only changed values, at most 5 requests a second.

A seed script first records what Attio holds, including the live Company and Person values. First dates only move earlier and last dates only later, so old mail leaving the window can't undo them.

Where Attio's strongest user is a mailbox the engine doesn't read, connection strength is left alone. An empty value is cleared; strength fades to Very weak. The engine refuses to write while `ATTIO_IS_TEST` is set.

`INTERACTIONS_ATTIO_WRITE_MODE` is `off` by default, and `dry_run` logs counts only. A production alarm fires after 30 minutes without a clean write round.

## Creating contacts

The engine can create the Person and Organization for an outside contact it meets. It is on in production and off by default elsewhere. See [Creating contacts from email](interactions-contact-creation.md).

## Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `INTERACTIONS_ENABLED` | `false` | Turns the loop on. Set it in one environment only. |
| `INTERACTIONS_POLL_INTERVAL_S` | `900` | Seconds between passes. At least 60. |
| `INTERACTIONS_MAILBOXES` | Jules and Ramzy | Primary addresses to read, separated by spaces. |
| `INTERACTIONS_INTERNAL_DOMAINS` | both company domains | Team domains. The first is the main one. |
| `INTERACTIONS_BACKFILL_MONTHS` | `12` | How far back the first read goes. |
| `INTERACTIONS_RETENTION_MONTHS` | `12` | How long interactions are kept. At least 1. |
| `INTERACTIONS_ATTIO_WRITE_MODE` | `off` | `off`, `dry_run` or `on`. Keep `off` until the shadow-week gate has passed. |
| `INTERACTIONS_ATTIO_WRITES_PER_SECOND` | `5` | Request rate to Attio. |
| `INTERACTIONS_ATTIO_MAX_RECORDS_PER_ROUND` | `500` | Most records written per object in one round. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | none | The service-account key. Secrets Manager only. |

The scoring settings, which are the points, half-life, bonus, and label cut-offs, start at the plan's values. They are tuned during the shadow week. The settings for [creating contacts](interactions-contact-creation.md) and the [Deal rollup](interactions-deal-rollup.md) are on their pages.

## Data stored

Five PostgreSQL tables hold the data: `interactions`, `interaction_participants`, `mailbox_sync_cursors`, `attio_sent_values`, and `interaction_review_items`. The first three hold headers, subjects, sender names, and event details, never bodies. The last two hold what was last sent to Attio and the cases waiting for review.

Subjects can contain deal names, so treat these tables like other CRM data. Nothing is sent to a third party.

## Safeguards and limits

- The loop stays off unless `INTERACTIONS_ENABLED` is true and the key is valid. A missing or malformed key is logged and never echoed.
- A database lock lets only one instance run a pass. This matters because dev and prod can share a database and a Google tenant.
- One failing mailbox is logged and doesn't stop the others.
- Gmail allows 6,000 quota units a minute per user, and each message fetch costs 20. The engine fetches at most 250 messages a minute per mailbox.
- A large backfill therefore takes hours. About 20,000 messages take about 80 minutes.
- If Google issues no Calendar sync token, each pass re-reads the last seven days instead.

## Shadow week

A read-only command compares our connection-strength label for each Organization with Attio's label on the matching Company. It writes nothing to Attio or PostgreSQL. Run it inside the deployed container once a week of data has settled.

The report prints the exact-match rate, the within-one-level rate, and a 5-by-5 table. Companies that aren't a fair comparison, such as those whose strongest user is `tech@` or a mailbox we don't read, are counted separately.

Writing to Attio starts only if at least 80% match exactly and 95% are within one level.

## Where to look

The code is in `server/app/modules/interactions` and `server/app/modules/google_workspace`. Each has a README and a HOW-TO-READ guide. Google access is its own module so other features can reuse it.
