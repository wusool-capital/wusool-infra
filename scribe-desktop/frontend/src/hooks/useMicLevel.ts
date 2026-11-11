import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';

const POLL_MS = 150;
const HISTORY = 3;
// Mirrors `SILENCE_DB` in audio/mic_level.rs; speech sits well above it.
const SILENCE_DB = -60;
const LOUD_DB = -10;

/** 0 (silent) to 1 (loud) for one dBFS reading. */
export function levelFraction(db: number): number {
  return Math.min(1, Math.max(0, (db - SILENCE_DB) / (LOUD_DB - SILENCE_DB)));
}

/**
 * The last few real microphone levels while `active`, newest last, so a meter can show
 * whether the mic actually hears anything. All zeros when inactive.
 */
export function useMicLevel(active: boolean): number[] {
  const [levels, setLevels] = useState<number[]>(() => Array(HISTORY).fill(0));

  useEffect(() => {
    if (!active) {
      setLevels(Array(HISTORY).fill(0));
      return;
    }
    let cancelled = false;
    const timer = setInterval(async () => {
      try {
        const db = await invoke<number>('get_mic_level');
        if (!cancelled) setLevels((prev) => [...prev.slice(1 - HISTORY), levelFraction(db)]);
      } catch {
        // A missed reading just leaves the meter where it was.
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [active]);

  return levels;
}
