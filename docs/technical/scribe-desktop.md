# WusoolScribe desktop app

WusoolScribe is a self-contained desktop application built with
[Tauri](https://tauri.app/): a Rust core with a Next.js frontend, packaged as
a single cross-platform app for macOS and Windows.

```text
┌─────────────────────────── WusoolScribe (desktop) ───────────────────────────┐
│  Next.js UI  ⇄  Rust core (Tauri)  ⇄  Audio engine, transcription, local DB   │
└────────────────────────────────────┬──────────────────────────────────────────┘
                                      │ pushes a finished transcript
                                      ▼
                                  Wusool server ──▶ AWS Bedrock (summarization)
                                                 └─▶ Attio (note)
```

## Local processing

- **Audio capture** — microphone and system audio captured simultaneously,
  with professional-grade mixing so neither drowns out the other.
- **Transcription** — local Whisper/Parakeet models, GPU-accelerated where
  available (Apple Silicon Metal/CoreML, NVIDIA CUDA, AMD/Intel Vulkan),
  falling back to CPU automatically.
- **Local database** — meeting metadata, transcripts, and summaries are
  stored on the device (SQLite).

## Server-side summarization

The desktop app itself never sends raw audio to the server. Once a meeting
is fully transcribed locally, the user can push the transcript to the
server for AI summarization — see the `meetings` server module. The server:

1. Accepts the push and acknowledges immediately (no waiting on the LLM
   call).
2. Summarizes the transcript via AWS Bedrock in the background.
3. Writes a structured CRM note, linked to the organization and
   buyer/seller role when one is resolved.
4. The desktop app polls for the result and syncs it back into the local
   meeting list.

## Distribution and updates

The app ships through a dedicated, versioned update feed and updates itself
automatically. Each release is cryptographically signed, and the app
verifies that signature before installing an update — so an update can only
ever come from a build Wusool actually published.
