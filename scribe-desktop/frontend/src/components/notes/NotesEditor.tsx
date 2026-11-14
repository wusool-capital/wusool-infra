'use client';

import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react';
import type { Block, PartialBlock } from '@blocknote/core';
import { en } from '@blocknote/core/locales';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/shadcn';
import '@blocknote/shadcn/style.css';
import { blocksToMarkdownSafely } from '@/lib/blocknote-markdown';
import { createAutosave, type NotesContent, type NotesSaveState } from '@/lib/notesAutosave';
import { cn } from '@/lib/utils';

export interface NotesEditorProps {
  initial: NotesContent | null;
  onSave: (content: NotesContent) => Promise<void>;
  onSaveStateChange?: (state: NotesSaveState) => void;
  /** Filled with a function that writes any pending edit right away. */
  flushRef?: MutableRefObject<(() => Promise<void>) | null>;
  placeholder?: string;
  autoFocus?: boolean;
  className?: string;
}

function parseBlocks(json: string | null | undefined): PartialBlock[] | undefined {
  if (!json) return undefined;
  try {
    const blocks = JSON.parse(json);
    return Array.isArray(blocks) && blocks.length > 0 ? blocks : undefined;
  } catch {
    return undefined;
  }
}

// Popup windows have no ThemeProvider, so follow the `.dark` class directly.
function useDarkClass(): boolean {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const root = document.documentElement;
    const update = () => setDark(root.classList.contains('dark'));
    update();
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return dark;
}

export default function NotesEditor({
  initial,
  onSave,
  onSaveStateChange,
  flushRef,
  placeholder = 'Write notes…',
  autoFocus = false,
  className,
}: NotesEditorProps) {
  const dark = useDarkClass();
  const initialBlocks = useMemo(() => parseBlocks(initial?.notes_json), [initial]);
  const editor = useCreateBlockNote({
    initialContent: initialBlocks,
    dictionary: { ...en, placeholders: { ...en.placeholders, emptyDocument: placeholder } },
  });

  const onSaveRef = useRef(onSave);
  onSaveRef.current = onSave;
  const onStateRef = useRef(onSaveStateChange);
  onStateRef.current = onSaveStateChange;

  const autosave = useMemo(
    () =>
      createAutosave<Block[]>(
        async (blocks) => {
          const { markdown } = await blocksToMarkdownSafely(editor, blocks, { source: 'notes' });
          await onSaveRef.current({
            notes_markdown: markdown?.trim() ? markdown : null,
            notes_json: JSON.stringify(blocks),
          });
        },
        (state) => onStateRef.current?.(state),
      ),
    [editor],
  );

  // Notes stored only as markdown (none today, but the column allows it) still open.
  useEffect(() => {
    if (initialBlocks || !initial?.notes_markdown) return;
    let cancelled = false;
    editor.tryParseMarkdownToBlocks(initial.notes_markdown).then((blocks) => {
      if (!cancelled) editor.replaceBlocks(editor.document, blocks);
    });
    return () => {
      cancelled = true;
    };
  }, [editor, initial, initialBlocks]);

  useEffect(() => {
    const unsubscribe = editor.onChange(() => autosave.schedule(editor.document));
    return () => {
      unsubscribe?.();
    };
  }, [editor, autosave]);

  useEffect(() => {
    if (flushRef) flushRef.current = autosave.flush;
    return () => {
      // Unmount (window switch, navigation) must not drop the last keystrokes.
      void autosave.flush();
      if (flushRef) flushRef.current = null;
    };
  }, [autosave, flushRef]);

  useEffect(() => {
    if (autoFocus) editor.focus();
  }, [editor, autoFocus]);

  return (
    <div className={cn('select-text [&_.bn-container]:!bg-transparent [&_.bn-editor]:!bg-transparent', className)}>
      <BlockNoteView editor={editor} theme={dark ? 'dark' : 'light'} />
    </div>
  );
}
