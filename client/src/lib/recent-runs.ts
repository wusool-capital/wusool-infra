import { useSyncExternalStore } from "react";
import { z } from "zod";

// No list-runs endpoint yet, so the sidebar remembers runs started on this device.
const STORAGE_KEY = "wusool.recent-runs";
const MAX_RUNS = 12;

const recentRunSchema = z.object({
  runId: z.uuid(),
  buyerName: z.string(),
  // The advisor's note isn't persisted server-side; kept here so the run page can show it.
  advisorContext: z.string().nullable().default(null),
  startedAt: z.string(),
});
export type RecentRun = z.output<typeof recentRunSchema>;

const listeners = new Set<() => void>();
let cache: { raw: string | null; runs: RecentRun[] } = { raw: null, runs: [] };

function parse(raw: string | null): RecentRun[] {
  try {
    const parsed = z.array(recentRunSchema).safeParse(JSON.parse(raw ?? "[]"));
    return parsed.success ? parsed.data : [];
  } catch {
    return [];
  }
}

function read(): RecentRun[] {
  let raw: string | null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch {
    return cache.runs;
  }
  if (raw !== cache.raw) cache = { raw, runs: parse(raw) };
  return cache.runs;
}

export function rememberRun(run: RecentRun): void {
  const runs = [run, ...read().filter((r) => r.runId !== run.runId)].slice(
    0,
    MAX_RUNS,
  );
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(runs));
  } catch {
    return;
  }
  listeners.forEach((notify) => {
    notify();
  });
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

const EMPTY: RecentRun[] = [];

export function findRecentRun(runId: string): RecentRun | undefined {
  return read().find((run) => run.runId === runId);
}

export function useRecentRuns(): RecentRun[] {
  return useSyncExternalStore(subscribe, read, () => EMPTY);
}
