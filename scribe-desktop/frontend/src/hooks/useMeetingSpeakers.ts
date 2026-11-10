import { useCallback, useEffect, useMemo, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { toast } from 'sonner';
import type { SpeakerLabel } from '@/types';
import {
  DiarizationOutcome,
  DiarizationRun,
  DiarizationUpdatedEvent,
  MeetingSpeaker,
  NamedSpeaker,
  SeparationState,
  SpeakerMerge,
  SpeakerOverview,
  SpeakerProfileSummary,
  SpeakerTarget,
  diarizedIndex,
  mergeTarget,
  speakerDisplayName,
} from '@/lib/speakers';

// Long enough to read the toast and reach Undo after noticing a mistake.
const UNDO_WINDOW_MS = 10_000;

export interface SpeakerNames {
  resolveName: (label: SpeakerLabel | null | undefined) => string | null;
  /** True once a diarized voice has a person's name, so unnamed ones can invite naming. */
  isNamed: (label: SpeakerLabel) => boolean;
  /** Present only for saved meetings, where diarized voices can be named. */
  rename?: (label: SpeakerLabel, name: string) => Promise<void>;
  /** The other voice in this meeting that naming `label` as `name` would combine it with, if any. */
  mergeTargetFor: (label: SpeakerLabel, name: string) => string | null;
  /** People already in the voice library, offered as suggestions when naming. */
  knownNames: string[];
  /** Voices separated for this meeting; zero means diarization has not produced any yet. */
  voiceCount: number;
  /** This meeting's voices in number order, as places a line can be moved to. */
  voices: SpeakerLabel[];
  /** Moves lines to another speaker; present only for saved meetings. */
  reassign?: (segmentIds: string[], target: SpeakerTarget) => Promise<void>;
  separation: SeparationState;
  /** Runs (or re-runs) speaker separation for a saved meeting. */
  separate?: () => Promise<void>;
  /** Every separated voice with its talk time, longest first, for naming them in one place. */
  overview: SpeakerOverview[];
  /** Re-reads names and talk time after the transcript itself changes. */
  refresh: () => Promise<void>;
}

/**
 * Speaker names for a transcript. `onLabelsChanged` fires when background diarization
 * finishes, since that rewrites which speaker each segment belongs to.
 */
export function useMeetingSpeakers(meetingId?: string, onLabelsChanged?: () => void): SpeakerNames {
  const [speakers, setSpeakers] = useState<MeetingSpeaker[]>([]);
  const [overview, setOverview] = useState<SpeakerOverview[]>([]);
  const [profiles, setProfiles] = useState<SpeakerProfileSummary[]>([]);
  const [selfName, setSelfName] = useState<string | null>(null);
  const [separation, setSeparation] = useState<SeparationState>({ status: 'idle' });

  const load = useCallback(async () => {
    try {
      setSelfName(await invoke<string | null>('get_self_speaker_name'));
      if (!meetingId) return;
      const [meetingSpeakers, library, voices, run] = await Promise.all([
        invoke<MeetingSpeaker[]>('get_meeting_speakers', { meetingId }),
        invoke<SpeakerProfileSummary[]>('list_speaker_profiles'),
        invoke<SpeakerOverview[]>('get_speaker_overview', { meetingId }),
        invoke<DiarizationRun | null>('get_diarization_status', { meetingId }),
      ]);
      // A run started before this meeting opened announced itself before we were listening.
      if (run) setSeparation({ status: 'running', run });
      setSpeakers(meetingSpeakers);
      setProfiles(library);
      setOverview(voices);
    } catch (error) {
      console.error('Failed to load speaker names:', error);
    }
  }, [meetingId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!meetingId) return;
    const unlisten = listen<DiarizationUpdatedEvent>('diarization-updated', (event) => {
      const payload = event.payload;
      if (payload.meeting_id !== meetingId) return;
      if (payload.status === 'running') {
        setSeparation({
          status: 'running',
          run: { started_at_ms: payload.started_at_ms, estimated_seconds: payload.estimated_seconds },
        });
        return;
      }
      setSeparation(payload.status === 'failed' ? { status: 'failed', error: payload.error } : { status: 'idle' });
      if (payload.status === 'completed') {
        load();
        onLabelsChanged?.();
      }
    });
    return () => {
      unlisten.then((stop) => stop());
    };
  }, [meetingId, load, onLabelsChanged]);

  const undoMerge = useCallback(
    async (merge: SpeakerMerge) => {
      try {
        await invoke('undo_speaker_merge', { meetingId, merge });
        await load();
        onLabelsChanged?.();
        toast.success('Voices separated again');
      } catch (error) {
        toast.error("Couldn't separate these voices", {
          description: `${String(error)}. Move their lines with Change Speaker instead.`,
        });
      }
    },
    [meetingId, load, onLabelsChanged],
  );

  const rename = useCallback(
    async (label: SpeakerLabel, name: string) => {
      const person = mergeTarget(label, name, speakers) ?? name.trim();
      const named = await invoke<NamedSpeaker>('name_meeting_speaker', { meetingId, label, name });
      await load();
      if (!named.merge) return;
      // Naming a voice after someone already in the meeting merges it, moving its lines.
      onLabelsChanged?.();
      const merge = named.merge;
      toast(`Combined with ${person}`, {
        description: 'Their lines are now under one name.',
        duration: UNDO_WINDOW_MS,
        action: { label: 'Undo', onClick: () => void undoMerge(merge) },
      });
    },
    [meetingId, load, onLabelsChanged, speakers, undoMerge],
  );

  const mergeTargetFor = useCallback(
    (label: SpeakerLabel, name: string) => mergeTarget(label, name, speakers),
    [speakers],
  );

  const reassign = useCallback(
    async (segmentIds: string[], target: SpeakerTarget) => {
      await invoke('reassign_transcript_speaker', { meetingId, segmentIds, target });
      await load();
      onLabelsChanged?.();
    },
    [meetingId, load, onLabelsChanged],
  );

  const voices = useMemo(
    () =>
      speakers
        .map((s) => s.label)
        .sort((a, b) => (diarizedIndex(a) ?? 0) - (diarizedIndex(b) ?? 0)),
    [speakers],
  );

  const resolveName = useCallback(
    (label: SpeakerLabel | null | undefined) => speakerDisplayName(label, speakers, selfName),
    [speakers, selfName],
  );

  const isNamed = useCallback(
    (label: SpeakerLabel) => speakers.some((s) => s.label === label && s.name !== null),
    [speakers],
  );

  const separate = useCallback(async () => {
    setSeparation({ status: 'running', run: { started_at_ms: null, estimated_seconds: null } });
    try {
      const outcome = await invoke<DiarizationOutcome>('diarize_meeting', { meetingId });
      // A run already in flight reports through its own event; everything else settles here.
      if (outcome.status === 'failed') setSeparation({ status: 'failed', error: outcome.error });
      else if (outcome.status !== 'already_running') setSeparation({ status: 'idle' });
    } catch (error) {
      setSeparation({ status: 'failed', error: String(error) });
    }
  }, [meetingId]);

  const knownNames = useMemo(() => profiles.map((p) => p.name), [profiles]);

  return {
    resolveName,
    isNamed,
    rename: meetingId ? rename : undefined,
    mergeTargetFor,
    knownNames,
    voiceCount: speakers.length,
    voices,
    reassign: meetingId ? reassign : undefined,
    separation,
    separate: meetingId ? separate : undefined,
    overview,
    refresh: load,
  };
}
