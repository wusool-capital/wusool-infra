'use client';

import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { emit, listen } from '@tauri-apps/api/event';
import { X } from 'lucide-react';
import { LiveNotesEditor } from '@/components/notes/LiveNotesEditor';
import { NotesSaveStatus } from '@/components/notes/NotesSaveStatus';
import { NOTEPAD_FLUSH_REQUEST, NOTEPAD_FLUSHED } from '@/lib/liveNotesFlush';
import type { NotesSaveState } from '@/lib/notesAutosave';
import { cn } from '@/lib/utils';

interface RecordingStateSnapshot {
  is_recording: boolean;
  is_paused: boolean;
  active_duration: number | null;
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(h ? 2 : 1, '0');
  return `${h ? `${h}:` : ''}${mm}:${String(s).padStart(2, '0')}`;
}

/** Floating, always-on-top notepad window for the meeting being recorded. */
export default function NotepadPage() {
  const [reloadKey, setReloadKey] = useState(0);
  const [saveState, setSaveState] = useState<NotesSaveState>('idle');
  const [recording, setRecording] = useState<RecordingStateSnapshot | null>(null);
  const [visible, setVisible] = useState(true);
  const flushRef = useRef<(() => Promise<void>) | null>(null);

  useEffect(() => {
    // Tells the main window the draft on disk is final, so it can take it back.
    const flushAndReport = async () => {
      await flushRef.current?.();
      await emit(NOTEPAD_FLUSHED);
    };
    // The panel is hidden, never destroyed, so each show must reload the draft.
    const unlistenVisibility = listen<boolean>('notepad-visibility', ({ payload }) => {
      setVisible(payload);
      if (payload) {
        setReloadKey((key) => key + 1);
      } else {
        void flushAndReport();
      }
    });
    const unlistenRequest = listen(NOTEPAD_FLUSH_REQUEST, () => void flushAndReport());
    return () => {
      unlistenVisibility.then((fn) => fn());
      unlistenRequest.then((fn) => fn());
    };
  }, []);

  // Only while shown: the hidden panel stays alive for the app's lifetime.
  useEffect(() => {
    if (!visible) return;
    const read = () =>
      invoke<RecordingStateSnapshot>('get_recording_state')
        .then(setRecording)
        .catch(() => {});
    read();
    const id = setInterval(read, 1000);
    return () => clearInterval(id);
  }, [visible]);

  const saveAndClose = async () => {
    await flushRef.current?.();
    await invoke('close_notepad');
  };

  const returnToApp = async () => {
    await saveAndClose();
    await invoke('focus_main_window_command').catch(() => {});
  };

  const paused = recording?.is_paused ?? false;

  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden rounded-xl border border-border bg-card text-foreground">
      <header data-tauri-drag-region className="flex h-11 shrink-0 cursor-grab items-center gap-2 border-b border-border px-3">
        <span
          aria-hidden
          className={cn('size-1.5 shrink-0 rounded-full', paused ? 'bg-muted-foreground' : 'bg-destructive')}
        />
        <h1 data-tauri-drag-region className="text-sm font-semibold">
          Notes
        </h1>
        {recording?.is_recording && recording.active_duration != null && (
          <span data-tauri-drag-region className="text-xs tabular-nums text-muted-foreground">
            {paused ? 'Paused' : formatDuration(recording.active_duration)}
          </span>
        )}
        <button
          type="button"
          onClick={() => void returnToApp()}
          className="ml-auto h-7 cursor-pointer rounded-md px-2 text-xs font-medium text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Return to app
        </button>
        {/* Popup windows have no TooltipProvider, so the hover label is plain CSS. */}
        <div className="group relative">
          <button
            type="button"
            onClick={() => void saveAndClose()}
            aria-label="Save and close"
            className="flex size-7 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="size-4" aria-hidden />
          </button>
          <span
            aria-hidden
            className="pointer-events-none absolute right-0 top-full z-10 mt-1 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-xs text-background opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
          >
            Save and close
          </span>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <LiveNotesEditor
          reloadKey={reloadKey}
          flushRef={flushRef}
          onSaveStateChange={setSaveState}
          autoFocus
          className="py-2 [&_.bn-editor]:!pl-12 [&_.bn-editor]:!pr-4"
        />
      </div>

      <footer className="flex h-7 shrink-0 items-center px-3">
        <NotesSaveStatus state={saveState} />
      </footer>
    </main>
  );
}
