'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { NotesSaveStatus } from './NotesSaveStatus';
import type { NotesContent, NotesSaveState } from '@/lib/notesAutosave';
import { cn } from '@/lib/utils';

const NotesEditor = dynamic(() => import('./NotesEditor'), { ssr: false });

interface MeetingNotesSyncEvent {
  meeting_id: string;
  synced: boolean;
}

interface MeetingNotesEditorProps {
  meetingId: string;
  /** Pushed meetings re-sync edits to the server; others send notes with the push. */
  isPushed: boolean;
  className?: string;
}

/** A saved meeting's notes, editable before and after it is pushed. */
export function MeetingNotesEditor({ meetingId, isPushed, className }: MeetingNotesEditorProps) {
  const [initial, setInitial] = useState<{ id: string; content: NotesContent | null } | null>(null);
  const [saveState, setSaveState] = useState<NotesSaveState>('idle');
  const [syncFailed, setSyncFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    invoke<NotesContent | null>('get_meeting_notes', { meetingId })
      .catch((error) => {
        console.error('Failed to load meeting notes:', error);
        return null;
      })
      .then((content) => {
        if (!cancelled) setInitial({ id: meetingId, content });
      });
    return () => {
      cancelled = true;
    };
  }, [meetingId]);

  useEffect(() => {
    const unlisten = listen<MeetingNotesSyncEvent>('meeting-notes-sync', ({ payload }) => {
      if (payload.meeting_id === meetingId) setSyncFailed(!payload.synced);
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [meetingId]);

  const save = (content: NotesContent) =>
    invoke<void>('save_meeting_notes', {
      meetingId,
      notesMarkdown: content.notes_markdown,
      notesJson: content.notes_json,
    });

  return (
    <div className={cn('flex h-full flex-col', className)}>
      <div className="flex h-12 shrink-0 items-center gap-3 px-6">
        <h2 className="text-sm font-semibold text-foreground">Notes</h2>
        <NotesSaveStatus
          state={saveState}
          savedLabel={isPushed && syncFailed ? 'Saved locally. Syncs when the server is reachable.' : undefined}
        />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {initial?.id === meetingId && (
          <NotesEditor
            key={meetingId}
            initial={initial.content}
            onSave={save}
            onSaveStateChange={setSaveState}
            placeholder={isPushed ? 'Write notes…' : 'Write notes. They go to the summary when you push.'}
            className="pb-16 pt-1"
          />
        )}
      </div>
    </div>
  );
}
