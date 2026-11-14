# WusoolScribe

## What it does

WusoolScribe records or imports meetings and transcribes them on the user's
Mac. It writes an editable summary, and can push a finished meeting to the
Toolkit server, which files it in Attio as a note.

## Components

- **Desktop app:** a Next.js interface inside Tauri, with a Rust core. The
  core handles audio capture, Whisper transcription, summary-provider calls,
  local SQLite storage, and the server client.
- **Server side:** the `meetings` module in the Toolkit, behind `/desktop/*`.
- **Update feed:** a private, versioned S3 bucket behind CloudFront, in the
  `scribe-updates` stack.

## Platforms and signing

Only **macOS on Apple silicon** is released. The repository contains code for
Windows and Linux, but no builds are published for them.

- Builds are **ad-hoc signed and not notarized**, because there is no Apple
  Developer account. A first install needs the quarantine flag removed with
  `xattr`, as described in the user guide.
- Because the ad-hoc signature changes with every build, macOS asks for
  microphone and screen-recording permission again after **every update**.
  This is an accepted trade-off.
- Update payloads are signed separately with minisign, and the app verifies
  that signature before installing.
- The webview's Content Security Policy allows inline styles
  (`'unsafe-inline'` in `style-src`), and `tauri.conf.json` sets
  `dangerousDisableAssetCspModification: ["style-src"]`. Without it, Tauri
  adds style hashes to the policy, WebKit then ignores `'unsafe-inline'`, and
  every `style="…"` attribute in the pre-rendered pages is dropped. The
  sidebar, for example, opened at the width of its content instead of the
  saved width. Scripts keep Tauri's hashes.

## Releases and updates

![How a Scribe update reaches users](../.gitbook/assets/scribe-release.svg)

The `scribe-release` workflow is run by hand, choosing a `stable` or `beta`
channel. The version is bumped by hand in three files, and the workflow
checks they agree before building. It then uploads the payload, uploads
`latest.json`, and invalidates CloudFront. The workflow publishes through an
OIDC role scoped to its own GitHub environment.

The app's updater only reads the **stable** channel, so a beta release
currently reaches nobody.

## Data flow

```text
microphone and system audio, or an imported file
  → local recording (mixed track, plus a meeting-audio-only track)
  → local Whisper transcription, tagged "me" (mic) or "others" (system)
  → local speaker diarization of the meeting audio after saving
  → user edits the transcript and names speakers, and types notes
  → local SQLite meeting and its notes
  → optional push to the Toolkit server
  → server-side Bedrock summary and Attio note
```

Audio and transcription stay on the Mac. Scribe has no local summary model:
the transcript leaves the Mac only when the user pushes it, and the Toolkit
server writes the summary.

## Meeting notes

Notes typed while recording go to `notes.draft.json` in the recording
folder, because the meeting has no ID until it is saved. Saving the meeting
moves the draft into the local `meeting_notes` table. That covers the normal
stop and the crash recovery path.

The floating notepad is the shared overlay panel, so it floats over
full-screen meeting apps and is kept out of screen shares. Only one of the
notepad and the main window edits the notes at a time.

The first push sends the notes as `user_notes` (markdown, at most 50,000
characters). The server stores them in `meetings.user_notes` and appends
them to the CRM note, in Attio and in `notes.content`, under an
**Advisor notes** heading. `meetings.summary` stays the summary alone. Later edits to a pushed meeting go to
`PUT …/user-notes` a few seconds after typing stops. The 60-second
background sync retries any that failed. A 404 or 422 stops the retries
until the next edit. The app refuses to save notes over the limit, so they
can't block a push.

## Speaker separation

Scribe labels your microphone with your name and separates other voices on
the Mac after the meeting. When automatic separation is off, it separates only
on request. See [speaker separation](scribe-speakers.md).

## After a push

![How a push reaches Attio](../.gitbook/assets/scribe-push.svg)

1. `POST /desktop/meetings` stores the transcript and the user's notes, then
   returns at once with status `summarizing`.
2. In the background, Bedrock writes a structured summary.
3. The server **always** creates an Attio note, with or without an
   organization. The note links to the organization and, when the role has
   an Attio entry, to its buyer or seller role. The server never creates
   organizations.
4. An Attio failure is logged; the meeting still completes on the server.

The summary format and proofread are described in
[summaries and proofread](scribe-summaries.md).

## Interfaces

Every `/desktop/*` call needs the shared desktop API key as a bearer token,
compared in constant time.

| Endpoint | Purpose |
| --- | --- |
| `GET /desktop/verify` | Checks the server address and key before Settings saves them. |
| `POST /desktop/meetings` | Accepts a transcript. Over 1.5 million characters returns 422; a repeated install and recording returns 409. |
| `GET /desktop/meetings/{meeting_id}` | One meeting's processing state and summary. `summary_text` is the same rendered text filed as the Attio note; the app writes it to `summary.md`. |
| `GET /desktop/meetings?install_id=…` | Meetings for an installation; 200 by default, at most 500. |
| `GET /desktop/companies/search` | Searches CRM organizations to link a meeting to. |
| `DELETE /desktop/meetings/{install_id}/{local_recording_id}` | Removes a meeting from the server and Attio; returns 204. |
| `PUT /desktop/meetings/{install_id}/{local_recording_id}/user-notes` | Replaces a pushed meeting's notes and rewrites the **Advisor notes** section of its note, Attio first; returns 204. A missing or deleted meeting returns 404. Doesn't rerun the summary. |
| `POST /desktop/transcripts/corrections` | Sends transcript lines, with speaker names and optional `context` (title, names, the user's vocabulary), to Bedrock for spelling suggestions. Returns each fix with a category, plus `failed_segment_ids` for lines in batches that errored. Nothing is stored. |
| `POST /desktop/feedback` | Records in-app feedback and emails the team. |

Internal Tauri commands aren't a public integration API.

## Deleting a meeting

Deleting from the server is idempotent. It returns 409 while the meeting is
still being summarized, unless it has stalled. It deletes the Attio note
first, then marks the server's note and meeting rows as removed; nothing is
hard-deleted. Publishing and deleting a meeting each record an activity
(`meeting.published`, `meeting.deleted`) attributed to the Scribe install.

## Feedback

Feedback is written to `feedback_submissions` first, so a 200 means it was
kept. Categories are bug, feature request, transcription quality, and other;
messages are capped at 4,000 characters. Limits are five per install and 20
per IP address, with 429 beyond that. The SES email to the team is
best-effort and is only sent when a sender and recipient are configured.

## Failure behavior

- Recordings and drafts are stored locally, so a network failure never loses
  a meeting.
- Transcription failures stay local and can be retried.
- A failed remote summary doesn't affect the local transcript.
- If diarization fails or the meeting has no meeting-audio track, segments
  keep the `others` label. The meeting is saved either way.
- On the server, authentication, summarization, and Attio filing are
  separate stages; the app polls for the result.

## Code

The app is in `scribe-desktop/`; the server side is
`server/app/modules/meetings`. The release workflow is
`.github/workflows/scribe-release.yml`, and the update feed is
`infrastructure/terraform/stacks/scribe-updates`.
