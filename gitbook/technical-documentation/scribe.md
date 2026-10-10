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

## Releases and updates

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
  → local recording
  → local Whisper transcription
  → user edits the transcript
  → summary provider chosen in Settings
  → local SQLite meeting
  → optional push to the Toolkit server
  → server-side Bedrock summary and Attio note
```

Audio and transcription stay on the Mac. Two summary providers run locally:
Ollama and a built-in model. The online ones are OpenAI, Claude, Groq,
OpenRouter, and a custom OpenAI-compatible endpoint. Remote providers receive the
transcript text when chosen.

## After a push

1. `POST /desktop/meetings` stores the transcript and returns at once with
   status `summarizing`.
2. In the background, Bedrock writes a structured summary.
3. The server **always** creates an Attio note, with or without an
   organization. The note links to the organization and, when the role has
   an Attio entry, to its buyer or seller role. The server never creates
   organizations.
4. An Attio failure is logged; the meeting still completes on the server.

A push for the same install and recording always returns 409, so pushing
again doesn't recover a failed meeting. Instead, a meeting stalled for 10
minutes is reset the next time its status is read, which re-runs the
summary.

## Interfaces

Every `/desktop/*` call needs the shared desktop API key as a bearer token,
compared in constant time.

| Endpoint | Purpose |
| --- | --- |
| `GET /desktop/verify` | Checks the server address and key before Settings saves them. |
| `POST /desktop/meetings` | Accepts a transcript. Over 1.5 million characters returns 422; a repeated install and recording returns 409. |
| `GET /desktop/meetings/{meeting_id}` | One meeting's processing state and summary. |
| `GET /desktop/meetings?install_id=…` | Meetings for an installation; 200 by default, at most 500. |
| `GET /desktop/companies/search` | Searches CRM organizations to link a meeting to. |
| `DELETE /desktop/meetings/{install_id}/{local_recording_id}` | Removes a meeting from the server and Attio; returns 204. |
| `POST /desktop/transcripts/corrections` | Sends transcript lines to Bedrock for spelling suggestions. Nothing is stored. |
| `POST /desktop/feedback` | Records in-app feedback and emails the team. |

Internal Tauri commands aren't a public integration API.

## Deleting a meeting

Deleting from the server is idempotent. It returns 409 while the meeting is
still being summarized, unless it has stalled. It deletes the Attio note
first, then marks the server's note and meeting rows as removed; nothing is
hard-deleted.

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
- On the server, authentication, summarization, and Attio filing are
  separate stages; the app polls for the result.

## Code

The app is in `scribe-desktop/`; the server side is
`server/app/modules/meetings`. The release workflow is
`.github/workflows/scribe-release.yml`, and the update feed is
`infrastructure/terraform/stacks/scribe-updates`.
