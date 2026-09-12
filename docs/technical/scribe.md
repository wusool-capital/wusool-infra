# WusoolScribe

## Purpose

WusoolScribe records or imports meetings, transcribes audio on the user's
computer, creates an editable summary, and can push the completed meeting to
the Wusool backend for CRM filing.

## Components

The desktop application uses a Next.js interface inside Tauri with a Rust core.
The core owns audio capture, Whisper transcription, summary-provider calls,
SQLite persistence, and the server client. The repository contains platform
dependencies for macOS, Windows, and Linux; client documentation should promise
only platforms for which signed release artifacts are actually published.

The update feed is a separate AWS stack using S3 and CloudFront. A manifest
selects the platform artifact and Tauri verifies the signed update.

## Data flow

```text
microphone/system audio or imported file
  → local recording/import
  → local Whisper transcription
  → user review
  → configured summary provider
  → local SQLite meeting
  → optional authenticated push to the Wusool backend
  → Bedrock server summary and Attio note
```

Audio and transcription happen locally. Summary data leaves the device when a
remote provider such as Claude, Groq, OpenRouter, or a custom endpoint is
selected. Ollama can keep summary generation local when it points to a local
instance. A CRM push sends the finished transcript and meeting metadata to the
configured Wusool server; the server then summarizes through Bedrock and files
a note in Attio.

## Dependencies and configuration

- Microphone permission is required. System-audio capture can require platform
  permissions and a virtual audio device.
- Whisper models and supported acceleration are selected locally.
- Summary settings choose a provider, model, endpoint, and required API key.
- Push Destination stores the backend URL and shared desktop API key. The app
  also sends an installation identifier for synchronization.
- Automatic updates require access to the CloudFront feed and a valid signing
  key in the release pipeline.

## Interfaces

| Backend endpoint | Purpose |
| --- | --- |
| `GET /desktop/verify` | Checks the configured server and API key before saving them. |
| `POST /desktop/meetings` | Accepts a transcript while summarization continues in the background. |
| `GET /desktop/meetings/{meeting_id}` | Returns one pushed meeting's processing state. |
| `GET /desktop/meetings?install_id=…` | Lists meetings associated with an installation. |
| `GET /desktop/companies/search` | Searches CRM organizations for meeting association. |

Every `/desktop/*` request uses `Authorization: Bearer <desktop-api-key>`.
Internal Tauri commands are not a public integration API.

### Meeting submission example

```http
POST /desktop/meetings
Authorization: Bearer <desktop-api-key>
Content-Type: application/json

{
  "install_id": "example-install",
  "local_recording_id": "meeting-2026-09-12",
  "duration_seconds": 12.5,
  "occurred_at": "2026-09-12T09:30:00Z",
  "transcript": [
    {"speaker": "Speaker 1", "start": 0, "end": 4.2, "text": "Synthetic example."}
  ]
}
```

An accepted request returns a generated `meeting_id`, status
`"summarizing"`, and `already_existed: false`. Poll the meeting endpoint for
the final typed summary. Invalid input returns `422`, an unknown company
reference returns `422`, and a repeated install/recording pair returns `409`.

## Processing and failures

Recordings and drafts persist locally, so a network failure does not erase the
meeting. Transcription failures remain local and can be retried after checking
the audio and model. Remote-summary failures do not make local transcription
unavailable.

The push endpoint returns before server-side Bedrock and Attio work finishes.
The app polls for completion or failure. Authentication, reachability,
summarization, and Attio filing are distinct stages; preserve the local meeting
and retry the push rather than recreate the recording.
