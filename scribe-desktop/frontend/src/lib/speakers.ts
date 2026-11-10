import type { SpeakerLabel } from '@/types';

// Mirrors the Rust `MeetingSpeaker` / `SpeakerProfileSummary` serialization.
export interface MeetingSpeaker {
  label: SpeakerLabel;
  profile_id: string | null;
  name: string | null;
}

export interface SpeakerProfileSummary {
  id: string;
  name: string;
  sample_count: number;
}

// Mirrors the Rust `SpeakerOverview` returned by get_speaker_overview.
export interface VoiceSample {
  segment_id: string;
  text: string;
  start: number;
  end: number;
}

export interface SpeakerOverview {
  label: SpeakerLabel;
  name: string | null;
  line_count: number;
  talk_seconds: number;
  sample: VoiceSample | null;
  suggestion: { profile_id: string; name: string } | null;
  /** Named by the voice library, not yet confirmed by the user. */
  auto_named: boolean;
}

/** "45 s", "14 min" or "1 h 5 min": how long a voice spoke, at a glance. */
export function formatTalkTime(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total} s`;
  const minutes = Math.round(total / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

// Mirrors the Rust `DiarizationStarted` / `DiarizationEvent` payloads.
// Mirrors the Rust `DiarizationRun`: both null while the run waits in the queue.
export interface DiarizationRun {
  started_at_ms: number | null;
  estimated_seconds: number | null;
}

export type DiarizationUpdatedEvent =
  | ({ meeting_id: string; status: 'running' } & DiarizationRun)
  | { meeting_id: string; status: 'completed'; speakers: number; auto_named: number }
  | { meeting_id: string; status: 'skipped'; reason: string }
  | { meeting_id: string; status: 'failed'; error: string };

// Mirrors the Rust `DiarizationOutcome` returned by the diarize_meeting command.
export type DiarizationOutcome =
  | { status: 'completed'; speakers: number; auto_named: number }
  | { status: 'skipped'; reason: string }
  | { status: 'failed'; error: string }
  | { status: 'already_running' };

export type SeparationState =
  | { status: 'idle' }
  | { status: 'running'; run: DiarizationRun }
  | { status: 'failed'; error: string };

// An estimate can only be wrong, so the bar waits short of full until the run really ends.
const MAX_ESTIMATED_PERCENT = 95;

/** Estimated progress of a run, or null while it has no estimate yet. */
export function separationProgress(
  run: DiarizationRun,
  nowMs: number,
): { percent: number; secondsLeft: number } | null {
  if (run.started_at_ms === null || run.estimated_seconds === null || run.estimated_seconds <= 0) return null;
  const elapsed = Math.max(0, (nowMs - run.started_at_ms) / 1000);
  return {
    percent: Math.min(MAX_ESTIMATED_PERCENT, (elapsed / run.estimated_seconds) * 100),
    secondsLeft: Math.max(0, Math.ceil(run.estimated_seconds - elapsed)),
  };
}

// Mirrors the Rust `SpeakerMerge`: what a merge changed, handed back to undo it.
export interface SpeakerMerge {
  kept: SpeakerLabel;
  kept_embedding: number[];
  kept_auto_named: boolean;
  merged: SpeakerLabel;
  merged_embedding: number[];
  merged_profile_id: string | null;
  merged_auto_named: boolean;
  segment_ids: string[];
}

// Mirrors the Rust `NamedSpeaker` returned by name_meeting_speaker.
export interface NamedSpeaker {
  label: SpeakerLabel;
  merge: SpeakerMerge | null;
}

/** The name of another voice in this meeting that naming `label` as `name` would combine it with. */
export function mergeTarget(label: SpeakerLabel, name: string, speakers: MeetingSpeaker[]): string | null {
  const typed = name.trim().toLowerCase();
  if (!typed) return null;
  return speakers.find((s) => s.label !== label && s.name?.toLowerCase() === typed)?.name ?? null;
}

// Mirrors the Rust `SpeakerTarget` taken by reassign_transcript_speaker.
export type SpeakerTarget = { kind: 'existing'; label: SpeakerLabel } | { kind: 'new' };

/** Index `n` of a `speaker_n` label, or null for "me"/"others". */
export function diarizedIndex(label: SpeakerLabel): number | null {
  const match = /^speaker_(\d+)$/.exec(label);
  return match ? Number(match[1]) : null;
}

/** Display name for a segment's speaker; must match `speaker_display_name` in push/mod.rs. */
export function speakerDisplayName(
  label: SpeakerLabel | null | undefined,
  speakers: MeetingSpeaker[],
  selfName: string | null,
): string | null {
  if (!label) return null;
  if (label === 'me') return selfName ?? 'Me';
  if (label === 'others') return 'Others';
  const named = speakers.find((s) => s.label === label)?.name;
  return named ?? `Speaker ${(diarizedIndex(label) ?? 0) + 1}`;
}
