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

/** The WAV bytes from `speaker_voice_clip`, whichever shape the IPC delivers them in. */
function toArrayBuffer(bytes: ArrayBuffer | number[]): ArrayBuffer {
  return bytes instanceof ArrayBuffer ? bytes : new Uint8Array(bytes).buffer;
}

/**
 * Plays a few seconds of each separated voice, one at a time.
 *
 * Decoded and played with Web Audio rather than an `<audio>` element: the
 * macOS webview serves the app from `tauri://`, and its media player can't
 * load `blob:` URLs there (NotSupportedError), so in-memory decoding is the
 * one path that works everywhere.
 */
export function useVoiceClip(meetingId?: string): VoiceClip {
  const [playing, setPlaying] = useState<SpeakerLabel | null>(null);
  const [loading, setLoading] = useState<SpeakerLabel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  // Keyed by the sample line too: re-separating renumbers voices, so a label alone can point at someone else.
  const buffersRef = useRef(new Map<string, AudioBuffer>());
  // Only the latest click may start playback; a slower earlier fetch is discarded.
  const requestRef = useRef(0);

  const stop = useCallback(() => {
    requestRef.current += 1;
    const source = sourceRef.current;
    sourceRef.current = null;
    if (source) {
      source.onended = null;
      source.stop();
    }
    setPlaying(null);
  }, []);

  useEffect(() => {
    const buffers = buffersRef.current;
    return () => {
      sourceRef.current?.stop();
      sourceRef.current = null;
      buffers.clear();
      void contextRef.current?.close();
      contextRef.current = null;
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
        const context = contextRef.current ?? new AudioContext();
        contextRef.current = context;
        // A context created outside a click starts suspended in WebKit.
        if (context.state === 'suspended') await context.resume();

        const key = `${label}:${sample.segment_id}:${sample.start}:${sample.end}`;
        let buffer = buffersRef.current.get(key);
        if (!buffer) {
          setLoading(label);
          const bytes = await invoke<ArrayBuffer | number[]>('speaker_voice_clip', { meetingId, label });
          buffer = await context.decodeAudioData(toArrayBuffer(bytes));
          buffersRef.current.set(key, buffer);
        }
        if (request !== requestRef.current) return;

        const source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);
        source.onended = () => {
          if (sourceRef.current === source) stop();
        };
        sourceRef.current = source;
        setPlaying(label);
        source.start();
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
