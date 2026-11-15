'use client';

import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { PictureInPicture2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { LiveNotesEditor } from '@/components/notes/LiveNotesEditor';
import { NotesSaveStatus } from '@/components/notes/NotesSaveStatus';
import { NOTEPAD_FLUSHED, registerLiveNotesFlush } from '@/lib/liveNotesFlush';
import type { NotesSaveState } from '@/lib/notesAutosave';

// If the notepad never reports its last save, take the draft back anyway.
const HANDOFF_FALLBACK_MS = 2000;

// editor: notes edited here. notepad: the floating notepad has them.
// handoff: the notepad closed and its last save is still landing.
type Mode = 'editor' | 'notepad' | 'handoff';

interface LiveNotesPanelProps {
  /** Stop has begun: notes are being saved with the meeting, so edits stop. */
  locked: boolean;
}

/** The notes side of the recording screen; hands off to the floating notepad. */
export function LiveNotesPanel({ locked }: LiveNotesPanelProps) {
  const [mode, setModeState] = useState<Mode>('editor');
  const modeRef = useRef<Mode>('editor');
  const setMode = (next: Mode) => {
    modeRef.current = next;
    setModeState(next);
  };
  const [reloadKey, setReloadKey] = useState(0);
  const [saveState, setSaveState] = useState<NotesSaveState>('idle');
  const flushRef = useRef<(() => Promise<void>) | null>(null);
  const lockedRef = useRef(locked);
  lockedRef.current = locked;

  useEffect(() => {
    registerLiveNotesFlush(() => flushRef.current?.() ?? Promise.resolve());
    return () => registerLiveNotesFlush(null);
  }, []);

  useEffect(() => {
    let fallback: ReturnType<typeof setTimeout> | undefined;
    const takeBack = () => {
      clearTimeout(fallback);
      // Once locked the draft may already be attached and gone; never reload it.
      if (modeRef.current !== 'handoff' || lockedRef.current) return;
      setReloadKey((key) => key + 1);
      setMode('editor');
    };

    invoke<boolean>('is_notepad_open')
      .then((open) => open && setMode('notepad'))
      .catch(() => {});
    const unlistenVisibility = listen<boolean>('notepad-visibility', ({ payload }) => {
      if (payload) {
        setMode('notepad');
        return;
      }
      if (modeRef.current === 'notepad') setMode('handoff');
      clearTimeout(fallback);
      fallback = setTimeout(takeBack, HANDOFF_FALLBACK_MS);
    });
    const unlistenFlushed = listen(NOTEPAD_FLUSHED, takeBack);
    return () => {
      clearTimeout(fallback);
      unlistenVisibility.then((fn) => fn());
      unlistenFlushed.then((fn) => fn());
    };
  }, []);

  const popOut = async () => {
    try {
      await flushRef.current?.();
      await invoke('open_notepad');
    } catch (error) {
      toast.error(String(error));
    }
  };

  return (
    <div className="flex h-full flex-col bg-notes">
      <div className="flex h-14 shrink-0 items-center justify-between gap-3 px-6">
        <div className="flex items-baseline gap-3">
          <h2 className="text-sm font-semibold text-foreground">Notes</h2>
          {mode === 'editor' && <NotesSaveStatus state={saveState} />}
        </div>
        {mode === 'editor' && !locked && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="size-8" onClick={popOut} aria-label="Open in floating notepad">
                <PictureInPicture2 />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Open in floating notepad</TooltipContent>
          </Tooltip>
        )}
      </div>

      {mode === 'editor' ? (
        <ScrollArea className="min-h-0 flex-1">
          <LiveNotesEditor
            reloadKey={reloadKey}
            flushRef={flushRef}
            onSaveStateChange={setSaveState}
            editable={!locked}
            autoFocus
            className="pb-32 pt-1"
          />
        </ScrollArea>
      ) : (
        <div className="flex flex-1 flex-col items-start gap-3 px-6 pt-2">
          {locked ? (
            <p className="max-w-sm text-sm text-muted-foreground">Your notes are being saved with the meeting.</p>
          ) : mode === 'notepad' ? (
            <>
              <p className="max-w-sm text-sm text-muted-foreground">
                Your notes are open in the floating notepad, on top of your other windows.
              </p>
              <Button size="sm" variant="outline" onClick={() => invoke('close_notepad')}>
                Bring notes back here
              </Button>
            </>
          ) : (
            <p className="max-w-sm text-sm text-muted-foreground">Bringing your notes back…</p>
          )}
        </div>
      )}
    </div>
  );
}
