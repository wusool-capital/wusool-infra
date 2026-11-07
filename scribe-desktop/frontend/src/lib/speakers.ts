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

// Mirrors the Rust `DiarizationStarted` / `DiarizationEvent` payloads.
export type DiarizationUpdatedEvent =
  | { meeting_id: string; status: 'running' }
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
  | { status: 'running' }
  | { status: 'failed'; error: string };

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
