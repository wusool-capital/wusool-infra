'use client';

import { useEffect, useState, type MutableRefObject } from 'react';
import dynamic from 'next/dynamic';
import { invoke } from '@tauri-apps/api/core';
import type { NotesContent, NotesSaveState } from '@/lib/notesAutosave';

const NotesEditor = dynamic(() => import('./NotesEditor'), { ssr: false });

interface LiveNotesEditorProps {
  /** Bump to reload the draft, e.g. after the other window edited it. */
  reloadKey: number;
  onSaveStateChange?: (state: NotesSaveState) => void;
  flushRef?: MutableRefObject<(() => Promise<void>) | null>;
  autoFocus?: boolean;
  className?: string;
}

const saveLiveNotes = (content: NotesContent) =>
  invoke<void>('save_live_notes', { notesMarkdown: content.notes_markdown, notesJson: content.notes_json });

/** Notes for the meeting being recorded, kept as a draft until it is saved. */
export function LiveNotesEditor({ reloadKey, onSaveStateChange, flushRef, autoFocus, className }: LiveNotesEditorProps) {
  const [draft, setDraft] = useState<{ key: number; content: NotesContent | null } | null>(null);

  useEffect(() => {
    let cancelled = false;
    invoke<NotesContent | null>('get_live_notes')
      .catch((error) => {
        console.error('Failed to load live notes:', error);
        return null;
      })
      .then((content) => {
        if (!cancelled) setDraft({ key: reloadKey, content });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (draft?.key !== reloadKey) return null;

  return (
    <NotesEditor
      key={draft.key}
      initial={draft.content}
      onSave={saveLiveNotes}
      onSaveStateChange={onSaveStateChange}
      flushRef={flushRef}
      autoFocus={autoFocus}
      className={className}
    />
  );
}
