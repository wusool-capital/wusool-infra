export type NotesSaveState = 'idle' | 'saving' | 'saved' | 'error';

/** Mirrors the Rust `LiveNotes` / `MeetingNotes` payloads. */
export interface NotesContent {
  notes_markdown: string | null;
  notes_json: string | null;
}

export interface Autosave<T> {
  schedule: (value: T) => void;
  flush: () => Promise<void>;
  cancel: () => void;
}

/**
 * Debounced, serialised saves: only the latest value is written, and saves
 * never overlap, so a slow write can't land after a newer one.
 */
export function createAutosave<T>(
  save: (value: T) => Promise<void>,
  onState: (state: NotesSaveState) => void,
  delayMs = 500,
): Autosave<T> {
  let pending: { value: T } | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let chain: Promise<void> = Promise.resolve();

  const run = (): Promise<void> => {
    if (timer) clearTimeout(timer);
    timer = null;
    if (!pending) return chain;
    const { value } = pending;
    pending = null;
    chain = chain.then(async () => {
      try {
        await save(value);
        if (!pending && !timer) onState('saved');
      } catch (error) {
        console.error('Failed to save notes:', error);
        onState('error');
      }
    });
    return chain;
  };

  return {
    schedule(value) {
      pending = { value };
      onState('saving');
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => void run(), delayMs);
    },
    flush: run,
    cancel() {
      if (timer) clearTimeout(timer);
      timer = null;
      pending = null;
    },
  };
}
