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
import { registerLiveNotesFlush } from '@/lib/liveNotesFlush';
import type { NotesSaveState } from '@/lib/notesAutosave';

// Lets the notepad's last debounced save land before the draft is reloaded here.
const NOTEPAD_HANDOFF_MS = 700;

/** The notes side of the recording screen; hands off to the floating notepad. */
export function LiveNotesPanel() {
  const [notepadOpen, setNotepadOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [saveState, setSaveState] = useState<NotesSaveState>('idle');
  const flushRef = useRef<(() => Promise<void>) | null>(null);

  useEffect(() => {
    registerLiveNotesFlush(() => flushRef.current?.() ?? Promise.resolve());
    return () => registerLiveNotesFlush(null);
  }, []);

  useEffect(() => {
    invoke<boolean>('is_notepad_open').then(setNotepadOpen).catch(() => {});
    const unlisten = listen<boolean>('notepad-visibility', ({ payload }) => {
      setNotepadOpen(payload);
      // The notepad edited the draft meanwhile; reopen it fresh.
      if (!payload) setTimeout(() => setReloadKey((key) => key + 1), NOTEPAD_HANDOFF_MS);
    });
    return () => {
      unlisten.then((fn) => fn());
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
    <div className="flex h-full flex-col bg-background">
      <div className="flex h-14 shrink-0 items-center justify-between gap-3 px-6">
        <div className="flex items-baseline gap-3">
          <h2 className="text-sm font-semibold text-foreground">Notes</h2>
          {!notepadOpen && <NotesSaveStatus state={saveState} />}
        </div>
        {!notepadOpen && (
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

      {notepadOpen ? (
        <div className="flex flex-1 flex-col items-start gap-3 px-6 pt-2">
          <p className="max-w-sm text-sm text-muted-foreground">
            Your notes are open in the floating notepad, on top of your other windows.
          </p>
          <Button size="sm" variant="outline" onClick={() => invoke('close_notepad')}>
            Bring notes back here
          </Button>
        </div>
      ) : (
        <ScrollArea className="min-h-0 flex-1">
          <LiveNotesEditor
            reloadKey={reloadKey}
            flushRef={flushRef}
            onSaveStateChange={setSaveState}
            autoFocus
            className="pb-32 pt-1"
          />
        </ScrollArea>
      )}
    </div>
  );
}
