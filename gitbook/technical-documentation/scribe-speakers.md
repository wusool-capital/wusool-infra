# WusoolScribe speaker separation

How Scribe labels who said what. Your own microphone carries your name.
Other voices are separated on the Mac after the meeting, or on request when
automatic separation is off. They're matched against a local voice library. See [WusoolScribe](scribe.md) for the rest of the app.

## How it works

Each transcript segment stores a speaker key: `me`, `others`, or
`speaker_N`. Display names are resolved from the meeting's speaker map, so
renaming a speaker changes one row.

- **Live:** the mic and system audio go through separate voice-activity
  detectors. A bleed gate drops mic audio that only echoes the speakers.
- **Imports:** imported lines start as `others`. With no `system.mp4`,
  separation reads the file that `metadata.json` names when its `source`
  is `import`. It runs after an import, as it does after a recording.
- **After saving:** [speakrs](https://github.com/avencera/speakrs), a Rust
  port of the pyannote `community-1` pipeline, runs on `system.mp4`. Each
  `others` segment gets the voice that overlaps it most. ffmpeg decodes the
  track straight to 16 kHz mono, so the audio buffer is about 230 MB per
  hour.
- **Backends:** CoreML by default on macOS, at about 90 times real time with
  a peak of about 2.7 GB. CPU runs at about 15 times real time on Apple
  silicon with a peak of about 0.5 GB. If CoreML fails, that run falls back
  to CPU. The CoreML models download only on request, from Settings or the
  prompt on **Separate Speakers**, whose **Use Slower Model** button switches
  the setting to CPU. Until then, automatic separation after a
  recording runs on CPU, so it never downloads 272 MB in the background.
- **Worker process:** separation runs in a child copy of the app, started
  with `--diarize-worker`, which prints its result as JSON. The app kills
  it if it runs past four times its estimate, or three minutes if longer.
  A CoreML run that fails or overruns retries once on CPU. The worker exits
  when its stdin closes, which the OS does however the app ends, including
  a force quit. So a stuck run never outlives Scribe, and killing it frees
  all its memory.
- **Automatic runs:** the `auto_separate` key in `diarization.json` (default
  on) controls whether separation starts after a recording is saved or an
  import finishes. Off, it runs only from **Separate Speakers**.
- **Progress:** speakrs reports no progress, so Scribe estimates it: 5
  seconds plus the audio length times the backend's rate. Rates start at
  0.065 (CPU) and 0.01 (CoreML) seconds per audio second. Each
  clean run of a minute or more blends its measured rate in at half weight,
  stored under `speed`. The `diarization-updated` running event carries
  `started_at_ms` and `estimated_seconds` once the run leaves the queue.
  `get_diarization_status` returns the same for a meeting opened mid-run.
  The bar stops at 95% until the run finishes.
- **Voice library:** naming a voice saves its embedding to
  `speaker_profiles`.
- **Merging:** naming a voice after a person another voice in the meeting
  already has merges them. Its lines move to that voice, the two embeddings
  are averaged into it, and its `meeting_speakers` row is deleted.
  `name_meeting_speaker` returns the label the voice ends up under and a
  snapshot of what the merge changed. `undo_speaker_merge` restores that
  snapshot: the row, its embedding, earlier name and `auto_named`, and its
  lines. It refuses when the meeting changed since, for example after
  separating speakers again or merging another voice into the same one.
- **Auto-naming:** a later meeting names a voice only on a clear match. Its
  cosine similarity must be at least 0.7 and lead the next-closest person by
  0.1. Two voices never get the same person. A close call stays unnamed
  and gets a one-click suggestion. `meeting_speakers.auto_named` marks
  auto-named voices until the user confirms or changes them.
- **Naming panel:** `get_speaker_overview` returns each voice's line
  count, talk time and a sample. The sample is the voice's longest
  uninterrupted turn, stored in `meeting_speakers.sample_start` and
  `sample_end` when separation runs. Transcript lines can hold several
  people, so a clip cut from a line could play someone else. The quote
  shown is the line that turn falls in. Voices added by hand, or separated
  before 0.8.6, fall back to their longest line.
  Unnamed voices scoring 0.5 or more against a profile not already in the
  meeting get a one-click suggestion. `speaker_voice_clip` cuts up to six
  seconds of the sample from `system.mp4` with ffmpeg and returns it
  as WAV bytes. The app decodes and plays them with the Web Audio API; the
  macOS webview can't play `blob:` URLs in an `<audio>` element.
- **Manual fixes:** `reassign_transcript_speaker` moves lines to a voice
  in the meeting, to `me`, or to a new `speaker_N`. A new voice has an
  empty embedding, so naming it never changes a profile's voice print. A
  re-run of separation replaces these changes.
- **Models:** pyannote segmentation finds who speaks when, and WeSpeaker
  ResNet34 turns each voice into the embedding the voice library compares.
  They download once from the `avencera/speakrs-models` Hugging Face
  repository (CC-BY-4.0).

Embeddings never leave the Mac. A push sends only the resolved names.
