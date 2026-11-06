# Incident: Google access for the interactions engine

## Purpose

Set up, rotate, revoke, and recover the Google service account that lets the
interactions engine read the team's Gmail and Calendar.

## Impact

The interactions engine stops reading new mail and meetings. Nothing else
depends on it yet: it writes nothing to Attio, and matching and the lead tools
don't use it. Interactions already stored stay in PostgreSQL.

## Symptoms

Look for these lines in the Toolkit CloudWatch log group.

- `interactions_not_started: GOOGLE_SERVICE_ACCOUNT_JSON is not set`, or
  `... is not valid`. The loop never started.
- `interactions_sync_failed mailbox=<address> source=<gmail|calendar>`. The
  traceback usually ends in `Google refused a token for <address>: <reason>`.
- `interactions_pass_skipped: another instance holds the lock` on every round.
  This is normal if a second instance runs the loop. It is a fault if only one
  does.
- `interactions_gmail_bookmark_expired` or
  `interactions_calendar_sync_token_expired`. Expected after a long outage; the
  engine recovers by itself.
- `interactions_calendar_no_sync_token`. Google issued no token, so the engine
  re-reads the last seven days of calendar on each pass.

## Severity

P3: nothing user-facing depends on it today. Raise it if a later stage writes
these fields to Attio.

## Set up

1. In the Google Cloud project that owns the service account, enable the Gmail
   API and the Google Calendar API.
2. Create the service account. It needs no IAM roles.
3. The organization blocks service-account keys by default through the
   `iam.disableServiceAccountKeyCreation` policy. An Organization Policy
   Administrator turns it off for this project only. Then create a JSON key.
4. Store the key as `GOOGLE_SERVICE_ACCOUNT_JSON` in the environment's toolkit
   secret in Secrets Manager. Delete the downloaded file. Never paste the key
   into chat, a ticket, a `.env` file, or the repository.
5. A Workspace super admin opens the Admin console, then Security, Access and
   data control, API controls, Manage Domain Wide Delegation. They add the
   service account's numeric Client ID with exactly these scopes, comma-separated:
   `https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/calendar.readonly`
6. Set `INTERACTIONS_MAILBOXES` to each mailbox's **primary** address, separated
   by spaces. Leave `tech@` out: it is a system inbox.
7. Set `INTERACTIONS_ENABLED=true` in **one** environment only. Development and
   production share one Google tenant. Then restart the Toolkit.
8. Watch the logs for an `interactions_pass written=...` line. The first pass
   backfills 12 months and can take hours for a large mailbox.

## Diagnosis

1. Read the log lines above to see which of the cases applies.
2. For `Google refused a token for <address>`, the reason comes from Google's
   token endpoint. Check that the delegation entry exists for this Client ID with
   both scopes, and that the address is a real primary mailbox. An alias isn't
   documented as accepted.
3. For HTTP 403 from Gmail or Calendar, check that both APIs are enabled in the
   project that owns the key.
4. For repeated HTTP 429, the mailbox has used its quota: 6,000 units a minute per
   user, where fetching one message costs 20. The engine paces itself to 250
   messages a minute, so look for another tool using the same mailbox.
5. For no `interactions_pass` lines at all, check `INTERACTIONS_ENABLED` and that
   the key parses.
6. To see whether a pass is running, check the advisory lock:
   `select pid, granted from pg_locks where locktype = 'advisory';`. A crashed
   process releases its lock by itself.

## Recovery

1. A missing or invalid key: store a valid key in the secret and restart the
   Toolkit.
2. A removed delegation or a missing scope: the admin re-adds it. The engine
   retries on every poll, so no restart is needed.
3. An expired bookmark or token: nothing to do. Gmail re-reads from the last sync
   minus one day, and Calendar re-reads its full window.
4. To rotate the key: create a new key, which needs the key-policy exception
   again. Update the secret, restart the Toolkit, then delete the old key in
   Google Cloud.
5. To stop reading at once: the admin deletes the delegation entry, and access
   ends at the next poll. To stop the loop as well, set `INTERACTIONS_ENABLED`
   to `false` and restart.

## Validation

- The logs show `interactions_pass written=<n> ... failures=0`.
- `select mailbox, source, last_synced_at, backfill_completed_at from
  mailbox_sync_cursors;` shows a row for each mailbox and source. `last_synced_at`
  is within the poll interval once the backfill is done.
- A test email to an outside contact appears in `interactions` after one poll.

## Rollback

Disabling the loop is the rollback. Stored interactions stay in PostgreSQL. The
engine never writes to Attio, so there is nothing to undo there. If mail must not
be kept, a data owner can delete the rows through an approved change. The
participants are deleted with them.

## Escalation

Escalate at once for a suspected key leak. Revoke first by deleting the
delegation entry, then rotate the key. The Workspace admins own the grant and the
Google Cloud project owner owns the key. Owners are NOT VERIFIED in this
repository.

## Do Not

- Do not widen the scopes beyond the two read-only ones.
- Do not turn the loop on in development and production at once.
- Do not store the key anywhere but Secrets Manager.
- Do not add `tech@` or any non-primary alias to `INTERACTIONS_MAILBOXES`.

## Root Cause Follow-Up

Record the failing mailbox, the Google error reason, and whether the delegation
entry or the key changed. Confirm that the first successful pass after the fix
shows `failures=0`.
