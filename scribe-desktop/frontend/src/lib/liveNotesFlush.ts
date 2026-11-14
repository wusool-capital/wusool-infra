import { invoke } from '@tauri-apps/api/core';
import { emit, listen } from '@tauri-apps/api/event';

// The notepad answers within this; past it the save goes ahead without it.
const NOTEPAD_FLUSH_TIMEOUT_MS = 2000;

export const NOTEPAD_FLUSH_REQUEST = 'notepad-flush-request';
export const NOTEPAD_FLUSHED = 'notepad-flushed';

// Lets the stop flow write pending live notes before the meeting is saved,
// without threading a ref through the recording page.
let flushLiveNotesImpl: (() => Promise<void>) | null = null;

export function registerLiveNotesFlush(flush: (() => Promise<void>) | null): void {
  flushLiveNotesImpl = flush;
}

async function requestNotepadFlush(): Promise<void> {
  let markFlushed: () => void = () => {};
  const flushed = new Promise<void>((resolve) => {
    markFlushed = resolve;
  });
  // Listen before asking, so a fast reply isn't missed.
  const unlisten = await listen(NOTEPAD_FLUSHED, () => markFlushed());
  const timer = setTimeout(markFlushed, NOTEPAD_FLUSH_TIMEOUT_MS);
  try {
    await emit(NOTEPAD_FLUSH_REQUEST);
    await flushed;
  } finally {
    clearTimeout(timer);
    unlisten();
  }
}

/** Writes every pending live-notes edit, in this window and the notepad. */
export async function flushLiveNotes(): Promise<void> {
  await flushLiveNotesImpl?.();
  if (await invoke<boolean>('notepad_exists').catch(() => false)) {
    await requestNotepadFlush();
  }
}
