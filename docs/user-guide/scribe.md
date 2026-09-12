# WusoolScribe

WusoolScribe is a desktop meeting assistant. It records and transcribes a
meeting on your computer, can generate an editable summary, and can send a
completed transcript to the Wusool server for filing in Attio.

Audio recording and speech-to-text processing stay on the computer. A cloud
summary provider receives transcript text when you choose that provider, and
the Wusool server receives the completed transcript when you push a meeting
to the CRM. Audio is not part of the CRM push.

## Install and prepare the app

### Prerequisites

- Use the current installer link supplied by your team.
- On macOS, allow microphone and screen-recording permissions. Capturing the
  other side of a call may require a virtual audio device such as BlackHole.
- On Windows, system-audio capture uses the built-in loopback facility.
- Allow internet access and time for the first launch to download a local
  transcription model.

On Windows, run the supplied installer. On macOS, open the supplied `.dmg`,
drag **WusoolScribe** to **Applications**, and launch it from there. The app
detects supported hardware acceleration automatically and falls back to CPU
transcription when necessary.

**Expected result:** the app opens, the local model finishes its first-time
download, and audio sources appear under **Devices**.

## Record and transcribe a meeting

1. Select the microphone and system-audio devices.
2. Optionally name the meeting, then press **Record**.
3. Confirm that transcript lines appear while people speak. You may copy the
   transcript at any time.
4. Pause when needed. Press **Stop** to finish and return it to the meeting
   list.

**Expected result:** the recording and timestamped transcript remain in the
local meeting list. You can choose the model and language before or between
recordings.

If only your voice is present, check the system-audio device and operating
system permissions. If no speech appears, check microphone selection and
input level before restarting.

## Summarize a meeting

After transcription, generate a summary using the provider configured in
**Settings**. Documented choices include local Ollama, Claude, Groq,
OpenRouter, and a custom OpenAI-compatible endpoint. Ollama keeps summary
processing local; cloud providers receive transcript text under that
provider's data-handling terms.

Review and edit every summary before sharing or filing it. Treat generated
content as a draft, especially names, figures, decisions, and actions.

## Import or enhance existing audio

**Import & Enhance is a beta feature.** Choose **Import**, select an audio
file, and let WusoolScribe transcribe it locally. For an existing meeting,
**Enhance** can re-transcribe it with another model or language.

**Expected result:** the imported or enhanced meeting appears with a new
local transcript. Keep the original audio until you check the result.

## Send a meeting to Attio

### One-time setup

In **Settings → Push Destination**, enter the server URL and API key supplied
by the engineering owner. The app validates them before saving. The screen
also shows the generated **Install ID**; include it in support requests.

### Steps

1. Open a completed meeting and review its transcript and summary.
2. When it concerns a company, search for and select that organization.
3. Press **Push**.

**Expected result:** the app acknowledges the push, the server processes the
transcript in the background, and status updates when the structured note is
filed in Attio. With an organization selected, the note links to its buyer or
seller record where one exists. A meeting without one becomes a general note.

You can close the app while processing continues. Avoid pushing again merely
because processing takes time. If it fails, verify destination settings and
use [Troubleshooting](troubleshooting.md).

## Updates and local data

WusoolScribe checks for signed updates automatically. Accept the prompt or
check **Settings → About**. Recordings and local transcripts remain on the
device; use **Settings** to see the storage location. Follow your
organization's retention rules when deleting or sharing meeting material.
