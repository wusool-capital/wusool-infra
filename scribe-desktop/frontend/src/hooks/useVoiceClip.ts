import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import type { SpeakerLabel } from '@/types';

export interface VoiceClip {
  playing: SpeakerLabel | null;
  loading: SpeakerLabel | null;
  error: string | null;
  toggle: (label: SpeakerLabel) => Promise<void>;
}

/** Plays a few seconds of each separated voice, one at a time. */
export function useVoiceClip(meetingId?: string): VoiceClip {
  const [playing, setPlaying] = useState<SpeakerLabel | null>(null);
  const [loading, setLoading] = useState<SpeakerLabel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Clips are cut by ffmpeg, so each is fetched once per meeting view.
  const urlsRef = useRef(new Map<SpeakerLabel, string>());

  const stop = useCallback(() => {
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
    async (label: SpeakerLabel) => {
      if (!meetingId) return;
      if (playing === label) {
        stop();
        return;
      }
      stop();
      setError(null);
      try {
        let url = urlsRef.current.get(label);
        if (!url) {
          setLoading(label);
          const bytes = await invoke<ArrayBuffer>('speaker_voice_clip', { meetingId, label });
          url = URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' }));
          urlsRef.current.set(label, url);
        }
        const audio = new Audio(url);
        audio.onended = () => {
          if (audioRef.current === audio) stop();
        };
        audioRef.current = audio;
        setPlaying(label);
        await audio.play();
      } catch (e) {
        stop();
        setError(String(e));
      } finally {
        setLoading(null);
      }
    },
    [meetingId, playing, stop],
  );

  return { playing, loading, error, toggle };
}
