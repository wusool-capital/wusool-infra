import { useCallback, useEffect, useMemo, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type { SpeakerLabel } from '@/types';
import {
  DiarizationOutcome,
  DiarizationUpdatedEvent,
  MeetingSpeaker,
  SeparationState,
  SpeakerOverview,
  SpeakerProfileSummary,
  speakerDisplayName,
} from '@/lib/speakers';

export interface SpeakerNames {
  resolveName: (label: SpeakerLabel | null | undefined) => string | null;
  /** True once a diarized voice has a person's name, so unnamed ones can invite naming. */
  isNamed: (label: SpeakerLabel) => boolean;
  /** Present only for saved meetings, where diarized voices can be named. */
  rename?: (label: SpeakerLabel, name: string) => Promise<void>;
  /** People already in the voice library, offered as suggestions when naming. */
  knownNames: string[];
  /** Voices separated for this meeting; zero means diarization has not produced any yet. */
  voiceCount: number;
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
      const [meetingSpeakers, library, voices] = await Promise.all([
        invoke<MeetingSpeaker[]>('get_meeting_speakers', { meetingId }),
        invoke<SpeakerProfileSummary[]>('list_speaker_profiles'),
        invoke<SpeakerOverview[]>('get_speaker_overview', { meetingId }),
      ]);
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
        setSeparation({ status: 'running' });
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

  const rename = useCallback(
    async (label: SpeakerLabel, name: string) => {
      await invoke('name_meeting_speaker', { meetingId, label, name });
      await load();
    },
    [meetingId, load],
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
    setSeparation({ status: 'running' });
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
    knownNames,
    voiceCount: speakers.length,
    separation,
    separate: meetingId ? separate : undefined,
    overview,
    refresh: load,
  };
}
