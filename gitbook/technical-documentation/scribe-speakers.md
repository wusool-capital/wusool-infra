# WusoolScribe speaker separation

How Scribe labels who said what. Your own microphone carries your name.
Other voices are separated on the Mac after the meeting and matched against a
local voice library. See [WusoolScribe](scribe.md) for the rest of the app.

## How it works

Each transcript segment stores a speaker key: `me`, `others`, or
`speaker_N`. Display names are resolved from the meeting's speaker map, so
renaming a speaker changes one row.

- **Live:** the mic and system audio go through separate voice-activity
  detectors. A bleed gate drops mic audio that only echoes the speakers.
- **After saving:** [speakrs](https://github.com/avencera/speakrs) 0.7, a
  Rust port of the pyannote `community-1` pipeline, runs on `system.mp4`. Each
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
- **Voice library:** naming a voice saves its embedding to
  `speaker_profiles`.
- **Auto-naming:** a later meeting names a voice only on a clear match. Its
  cosine similarity must be at least 0.7 and lead the next-closest person by
  0.1. Two voices never get the same person. A close call stays unnamed
  and gets a one-click suggestion. `meeting_speakers.auto_named` marks
  auto-named voices until the user confirms or changes them.
- **Naming panel:** `get_speaker_overview` returns each voice's line
  count, talk time and a sample line (the longest of its first five).
  Unnamed voices scoring 0.5 or more against a profile not already in the
  meeting get a one-click suggestion. `speaker_voice_clip` cuts up to six
  seconds of the sample line from `system.mp4` with ffmpeg and returns it
  as WAV bytes, played from a `blob:` URL (allowed by `media-src`).
- **Models:** three parts, as in pyannote `community-1`:
  - `segmentation-3.0` (pyannote) finds who speaks when.
  - `wespeaker-voxceleb-resnet34` (WeSpeaker ResNet34, trained on
    VoxCeleb) turns each voice into the embedding the voice library compares.
  - PLDA (the `plda_*` files) clusters the segments into speakers.
- **Model files:** about 32 MB for CPU, plus 272 MB of CoreML bundles of the
  same models. They download once into the app data folder from the
  `avencera/speakrs-models` Hugging Face repository (CC-BY-4.0). Revision
  `67f963b6a1d94fcd4678948237b3cc8bd69bf1d8` is pinned in `engine.rs`.

Embeddings never leave the Mac. A push sends only the resolved names.
