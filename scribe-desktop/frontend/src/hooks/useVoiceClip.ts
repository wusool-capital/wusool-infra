import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import type { SpeakerLabel } from '@/types';
import type { VoiceSample } from '@/lib/speakers';

export interface VoiceClip {
  playing: SpeakerLabel | null;
  loading: SpeakerLabel | null;
  error: string | null;
  toggle: (label: SpeakerLabel, sample: VoiceSample) => Promise<void>;
}

/** Plays a few seconds of each separated voice, one at a time. */
export function useVoiceClip(meetingId?: string): VoiceClip {
  const [playing, setPlaying] = useState<SpeakerLabel | null>(null);
  const [loading, setLoading] = useState<SpeakerLabel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Keyed by the sample line too: re-separating renumbers voices, so a label alone can point at someone else.
  const urlsRef = useRef(new Map<string, string>());
  // Only the latest click may start playback; a slower earlier fetch is discarded.
  const requestRef = useRef(0);

  const stop = useCallback(() => {
    requestRef.current += 1;
    audioRef.current?.pause();
    audioRef.current = null;
    setPlaying(null);
  }, []);

  useEffect(() => {
    const urls = urlsRef.current;
    return () => {
      audioRef.current?.pause();
      urls.forEach((url) => URL.revokeObjectURL(url));
      urls.clear();
    };
  }, [meetingId]);

  const toggle = useCallback(
    async (label: SpeakerLabel, sample: VoiceSample) => {
      if (!meetingId) return;
      if (playing === label) {
        stop();
        return;
      }
      stop();
      const request = requestRef.current;
      setError(null);
      try {
        const key = `${label}:${sample.segment_id}:${sample.start}:${sample.end}`;
        let url = urlsRef.current.get(key);
        if (!url) {
          setLoading(label);
          const bytes = await invoke<ArrayBuffer>('speaker_voice_clip', { meetingId, label });
          url = URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' }));
          urlsRef.current.set(key, url);
        }
        if (request !== requestRef.current) return;
        const audio = new Audio(url);
        audio.onended = () => {
          if (audioRef.current === audio) stop();
        };
        audioRef.current = audio;
        setPlaying(label);
        await audio.play();
      } catch (e) {
        if (request !== requestRef.current) return;
        stop();
        setError(String(e));
      } finally {
        setLoading((current) => (current === label ? null : current));
      }
    },
    [meetingId, playing, stop],
  );

  return { playing, loading, error, toggle };
}
