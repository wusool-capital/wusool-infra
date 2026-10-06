// Mirrors the Rust `TranscriptRow` / `TranscriptEdit` serialization (snake_case).
export interface TranscriptRow {
  id: string;
  meeting_id: string;
  transcript: string;
  timestamp: string;
  audio_start_time: number | null;
  audio_end_time: number | null;
  duration: number | null;
  speaker: string | null;
}

export interface TranscriptEdit {
  before: TranscriptRow[];
  after: TranscriptRow[];
}

export interface TranscriptMatches {
  segment_ids: string[];
  match_count: number;
}

export interface CorrectionSuggestion {
  segment_id: string;
  original: string;
  suggested: string;
  reason: string;
}

export type SelectMode = 'single' | 'range' | 'toggle';

export interface SelectionState {
  selected: ReadonlySet<string>;
  anchor: string | null;
}

export const EMPTY_SELECTION: SelectionState = { selected: new Set(), anchor: null };

/**
 * `order` is the visible segment order. Range mode extends from the anchor,
 * which stays put so repeated shift-clicks pivot around the same line.
 */
export function updateSelection(
  state: SelectionState,
  order: readonly string[],
  id: string,
  mode: SelectMode,
): SelectionState {
  if (mode === 'range' && state.anchor !== null) {
    const from = order.indexOf(state.anchor);
    const to = order.indexOf(id);
    if (from !== -1 && to !== -1) {
      const [lo, hi] = from < to ? [from, to] : [to, from];
      return { selected: new Set(order.slice(lo, hi + 1)), anchor: state.anchor };
    }
  }
  if (mode === 'toggle') {
    const next = new Set(state.selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return { selected: next, anchor: id };
  }
  return { selected: new Set([id]), anchor: id };
}

/** Ids of every segment that comes before `id` in `order`. */
export function idsBefore(order: readonly string[], id: string): string[] {
  const index = order.indexOf(id);
  return index <= 0 ? [] : order.slice(0, index);
}

export interface RowOps {
  deleteIds: string[];
  rows: TranscriptRow[];
}

/** Rows to write to move from `from` to `to`; ids only in `from` are removed. */
function opsBetween(from: TranscriptRow[], to: TranscriptRow[]): RowOps {
  const target = new Set(to.map((r) => r.id));
  return {
    deleteIds: from.filter((r) => !target.has(r.id)).map((r) => r.id),
    rows: to,
  };
}

export const undoOps = (edit: TranscriptEdit): RowOps => opsBetween(edit.after, edit.before);
export const redoOps = (edit: TranscriptEdit): RowOps => opsBetween(edit.before, edit.after);

export interface EditHistory {
  undo: TranscriptEdit[];
  redo: TranscriptEdit[];
}

export const EMPTY_HISTORY: EditHistory = { undo: [], redo: [] };

// A new edit invalidates the redo branch, like any text editor.
export function recordEdit(history: EditHistory, edit: TranscriptEdit): EditHistory {
  return { undo: [...history.undo, edit], redo: [] };
}

export function popUndo(history: EditHistory): { edit: TranscriptEdit; history: EditHistory } | null {
  const edit = history.undo[history.undo.length - 1];
  if (!edit) return null;
  return { edit, history: { undo: history.undo.slice(0, -1), redo: [...history.redo, edit] } };
}

export function popRedo(history: EditHistory): { edit: TranscriptEdit; history: EditHistory } | null {
  const edit = history.redo[history.redo.length - 1];
  if (!edit) return null;
  return { edit, history: { undo: [...history.undo, edit], redo: history.redo.slice(0, -1) } };
}

/** A suggestion goes stale once the line no longer reads as the model saw it. */
export function activeSuggestions(
  suggestions: readonly CorrectionSuggestion[],
  textById: ReadonlyMap<string, string>,
): CorrectionSuggestion[] {
  return suggestions.filter((s) => textById.get(s.segment_id) === s.original);
}

export interface DiffSpan {
  prefix: string;
  removed: string;
  added: string;
  suffix: string;
}

/** Isolates the changed region between two lines, snapped to whole words. */
export function diffSpan(original: string, suggested: string): DiffSpan {
  const max = Math.min(original.length, suggested.length);

  let p = 0;
  while (p < max && original[p] === suggested[p]) p++;
  while (p > 0 && original[p - 1] !== ' ') p--;

  let s = 0;
  while (s < max - p && original[original.length - 1 - s] === suggested[suggested.length - 1 - s]) s++;
  while (s > 0 && original[original.length - s] !== ' ') s--;

  return {
    prefix: original.slice(0, p),
    removed: original.slice(p, original.length - s),
    added: suggested.slice(p, suggested.length - s),
    suffix: original.slice(original.length - s),
  };
}
