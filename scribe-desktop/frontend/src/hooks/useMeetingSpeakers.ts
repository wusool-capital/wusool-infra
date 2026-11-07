import { useCallback, useEffect, useMemo, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type { SpeakerLabel } from '@/types';
import {
  DiarizationUpdatedEvent,
  MeetingSpeaker,
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
}

/**
 * Speaker names for a transcript. `onLabelsChanged` fires when background diarization
 * finishes, since that rewrites which speaker each segment belongs to.
 */
export function useMeetingSpeakers(meetingId?: string, onLabelsChanged?: () => void): SpeakerNames {
  const [speakers, setSpeakers] = useState<MeetingSpeaker[]>([]);
  const [profiles, setProfiles] = useState<SpeakerProfileSummary[]>([]);
  const [selfName, setSelfName] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setSelfName(await invoke<string | null>('get_self_speaker_name'));
      if (!meetingId) return;
      const [meetingSpeakers, library] = await Promise.all([
        invoke<MeetingSpeaker[]>('get_meeting_speakers', { meetingId }),
        invoke<SpeakerProfileSummary[]>('list_speaker_profiles'),
      ]);
      setSpeakers(meetingSpeakers);
      setProfiles(library);
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
      if (event.payload.meeting_id !== meetingId || event.payload.status !== 'completed') return;
      load();
      onLabelsChanged?.();
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

  const knownNames = useMemo(() => profiles.map((p) => p.name), [profiles]);

  return { resolveName, isNamed, rename: meetingId ? rename : undefined, knownNames };
}
