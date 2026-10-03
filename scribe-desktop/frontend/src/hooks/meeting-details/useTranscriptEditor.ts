import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { toast } from 'sonner';
import { TranscriptSegmentData } from '@/types';
import {
  CorrectionSuggestion,
  EMPTY_HISTORY,
  EMPTY_SELECTION,
  EditHistory,
  SelectMode,
  SelectionState,
  TranscriptEdit,
  TranscriptMatches,
  activeSuggestions,
  idsBefore,
  popRedo,
  popUndo,
  recordEdit,
  redoOps,
  undoOps,
  updateSelection,
} from '@/lib/transcriptEditor';

// Below this, removing lines is obvious enough that a toast would be noise.
const UNDO_TOAST_THRESHOLD = 20;

interface UseTranscriptEditorProps {
  meetingId: string;
  segments: TranscriptSegmentData[];
  editable: boolean;
  /** Re-reads the loaded range from the DB after an edit lands. */
  reload: () => Promise<void>;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function useTranscriptEditor({ meetingId, segments, editable, reload }: UseTranscriptEditorProps) {
  const [selection, setSelection] = useState<SelectionState>(EMPTY_SELECTION);
  const [history, setHistoryState] = useState<EditHistory>(EMPTY_HISTORY);
  const [suggestions, setSuggestions] = useState<CorrectionSuggestion[]>([]);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [findOpen, setFindOpen] = useState(false);

  // Mirrors state so async handlers and the key listener never read a stale stack.
  const historyRef = useRef(history);
  const busyRef = useRef(false);
  const setHistory = useCallback((next: EditHistory) => {
    historyRef.current = next;
    setHistoryState(next);
  }, []);

  const order = useMemo(() => segments.map((s) => s.id), [segments]);

  // Drop selections for lines that no longer exist (deleted, merged away).
  useEffect(() => {
    setSelection((prev) => {
      const live = new Set(order);
      const kept = [...prev.selected].filter((id) => live.has(id));
      if (kept.length === prev.selected.size) return prev;
      return { selected: new Set(kept), anchor: prev.anchor && live.has(prev.anchor) ? prev.anchor : null };
    });
  }, [order]);

  const visibleSuggestions = useMemo(() => {
    const textById = new Map(segments.map((s) => [s.id, s.text]));
    return new Map(activeSuggestions(suggestions, textById).map((s) => [s.segment_id, s]));
  }, [segments, suggestions]);

  const select = useCallback(
    (id: string, mode: SelectMode) => setSelection((prev) => updateSelection(prev, order, id, mode)),
    [order],
  );
  const clearSelection = useCallback(() => setSelection(EMPTY_SELECTION), []);
  const selectAll = useCallback(
    () => setSelection({ selected: new Set(order), anchor: order[0] ?? null }),
    [order],
  );

  // Serializes edits: two overlapping DB writes would corrupt the undo stack.
  const guarded = useCallback(
    async <T,>(failure: string, run: () => Promise<T>): Promise<T | undefined> => {
      if (!editable || busyRef.current) return undefined;
      busyRef.current = true;
      try {
        return await run();
      } catch (error) {
        console.error(failure, error);
        toast.error(`${failure}: ${errorMessage(error)}`);
        return undefined;
      } finally {
        busyRef.current = false;
      }
    },
    [editable],
  );

  const commit = useCallback(
    async (edit: TranscriptEdit) => {
      setHistory(recordEdit(historyRef.current, edit));
      await reload();
    },
    [reload, setHistory],
  );

  const applyOps = useCallback(
    async (edit: TranscriptEdit, direction: 'undo' | 'redo') => {
      const ops = direction === 'undo' ? undoOps(edit) : redoOps(edit);
      await invoke('apply_transcript_edit', { meetingId, deleteIds: ops.deleteIds, rows: ops.rows });
      await reload();
    },
    [meetingId, reload],
  );

  const undo = useCallback(
    () =>
      guarded('Undo failed', async () => {
        const popped = popUndo(historyRef.current);
        if (!popped) return;
        await applyOps(popped.edit, 'undo');
        setHistory(popped.history);
      }),
    [guarded, applyOps, setHistory],
  );

  const redo = useCallback(
    () =>
      guarded('Redo failed', async () => {
        const popped = popRedo(historyRef.current);
        if (!popped) return;
        await applyOps(popped.edit, 'redo');
        setHistory(popped.history);
      }),
    [guarded, applyOps, setHistory],
  );

  const editTextRaw = useCallback(
    (segmentId: string, text: string) =>
      invoke<TranscriptEdit>('edit_transcript_segment', { meetingId, segmentId, text }),
    [meetingId],
  );

  const editText = useCallback(
    (segmentId: string, text: string) =>
      guarded('Failed to save edit', async () => {
        await commit(await editTextRaw(segmentId, text));
        return true;
      }),
    [guarded, commit, editTextRaw],
  );

  const deleteSegments = useCallback(
    (ids: string[]) =>
      guarded('Failed to remove lines', async () => {
        if (ids.length === 0) return;
        const edit = await invoke<TranscriptEdit>('delete_transcript_segments', { meetingId, segmentIds: ids });
        setSelection(EMPTY_SELECTION);
        await commit(edit);
        if (ids.length > UNDO_TOAST_THRESHOLD) {
          toast(`Removed ${ids.length} lines`, { action: { label: 'Undo', onClick: () => void undo() } });
        }
      }),
    [guarded, meetingId, commit, undo],
  );

  const deleteSelected = useCallback(
    () => deleteSegments(order.filter((id) => selection.selected.has(id))),
    [deleteSegments, order, selection],
  );

  const deleteBefore = useCallback((id: string) => deleteSegments(idsBefore(order, id)), [deleteSegments, order]);

  const mergeSegments = useCallback(
    (ids: string[]) =>
      guarded('Failed to merge lines', async () => {
        const positions = ids.map((id) => order.indexOf(id)).sort((a, b) => a - b);
        const adjacent = positions.every((p, i) => p !== -1 && (i === 0 || p === positions[i - 1] + 1));
        if (positions.length < 2 || !adjacent) {
          toast.error('Select two or more adjacent lines to merge');
          return;
        }
        const edit = await invoke<TranscriptEdit>('merge_transcript_segments', { meetingId, segmentIds: ids });
        setSelection(EMPTY_SELECTION);
        await commit(edit);
      }),
    [guarded, order, meetingId, commit],
  );

  const mergeSelected = useCallback(
    () => mergeSegments(order.filter((id) => selection.selected.has(id))),
    [mergeSegments, order, selection],
  );

  const mergeWithNext = useCallback(
    (id: string) => {
      const next = order[order.indexOf(id) + 1];
      if (next === undefined) {
        toast.error('This is the last loaded line');
        return undefined;
      }
      return mergeSegments([id, next]);
    },
    [mergeSegments, order],
  );

  const splitAt = useCallback(
    (segmentId: string, cursor: number) =>
      guarded('Failed to split line', async () => {
        const edit = await invoke<TranscriptEdit>('split_transcript_segment', { meetingId, segmentId, cursor });
        await commit(edit);
      }),
    [guarded, meetingId, commit],
  );

  const findMatches = useCallback(
    (query: string) => invoke<TranscriptMatches>('find_in_transcripts', { meetingId, query }),
    [meetingId],
  );

  const replaceAll = useCallback(
    (find: string, replacement: string) =>
      guarded('Replace failed', async () => {
        const edit = await invoke<TranscriptEdit>('replace_in_transcripts', {
          meetingId,
          find,
          replacement,
          segmentIds: null,
        });
        if (edit.after.length > 0) await commit(edit);
        return edit.after.length;
      }),
    [guarded, meetingId, commit],
  );

  const requestSuggestions = useCallback(async () => {
    setIsSuggesting(true);
    try {
      const result = await invoke<CorrectionSuggestion[]>('suggest_transcript_corrections', { meetingId });
      setSuggestions(result);
      if (result.length === 0) toast.success('No corrections suggested');
    } catch (error) {
      console.error('Failed to get suggestions:', error);
      toast.error(`Could not get suggestions: ${errorMessage(error)}`);
    } finally {
      setIsSuggesting(false);
    }
  }, [meetingId]);

  const dismissSuggestion = useCallback(
    (segmentId: string) => setSuggestions((prev) => prev.filter((s) => s.segment_id !== segmentId)),
    [],
  );

  const acceptSuggestion = useCallback(
    async (suggestion: CorrectionSuggestion) => {
      if (await editText(suggestion.segment_id, suggestion.suggested)) {
        dismissSuggestion(suggestion.segment_id);
      }
    },
    [editText, dismissSuggestion],
  );

  // One undo step for the whole batch, so Cmd+Z reverts every accepted fix at once.
  const acceptAllSuggestions = useCallback(
    () =>
      guarded('Failed to apply suggestions', async () => {
        const batch: TranscriptEdit = { before: [], after: [] };
        for (const suggestion of visibleSuggestions.values()) {
          const edit = await editTextRaw(suggestion.segment_id, suggestion.suggested);
          batch.before.push(...edit.before);
          batch.after.push(...edit.after);
        }
        if (batch.after.length > 0) await commit(batch);
        setSuggestions([]);
      }),
    [guarded, visibleSuggestions, editTextRaw, commit],
  );

  // The listener is registered once and reads the latest actions through a ref.
  const actionsRef = useRef({ undo, redo, deleteSelected, clearSelection, hasSelection: false });
  actionsRef.current = { undo, redo, deleteSelected, clearSelection, hasSelection: selection.selected.size > 0 };

  useEffect(() => {
    if (!editable) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (document.querySelector('[role="dialog"], [role="alertdialog"]')) return;
      const mod = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();

      if (mod && key === 'f') {
        event.preventDefault();
        setFindOpen(true);
        return;
      }

      // Inside a text field these belong to the browser (typing undo, backspace).
      const target = event.target as HTMLElement | null;
      if (target?.closest('textarea, input, [contenteditable="true"]')) return;

      const actions = actionsRef.current;
      if (mod && key === 'z') {
        event.preventDefault();
        void (event.shiftKey ? actions.redo() : actions.undo());
      } else if (mod && key === 'y') {
        event.preventDefault();
        void actions.redo();
      } else if (key === 'escape') {
        actions.clearSelection();
      } else if ((key === 'delete' || key === 'backspace') && actions.hasSelection) {
        event.preventDefault();
        void actions.deleteSelected();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [editable]);

  return {
    selectedIds: selection.selected,
    select,
    clearSelection,
    selectAll,
    canUndo: history.undo.length > 0,
    canRedo: history.redo.length > 0,
    undo,
    redo,
    editText,
    deleteSelected,
    deleteBefore,
    mergeSelected,
    mergeWithNext,
    splitAt,
    findOpen,
    setFindOpen,
    findMatches,
    replaceAll,
    suggestions: visibleSuggestions,
    isSuggesting,
    requestSuggestions,
    acceptSuggestion,
    dismissSuggestion,
    acceptAllSuggestions,
  };
}

export type TranscriptEditorApi = ReturnType<typeof useTranscriptEditor>;
