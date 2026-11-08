// Mirrors the Rust `TranscriptRow` / `TranscriptEdit` serialization (snake_case).
import type { SpeakerLabel } from "@/types";
export interface TranscriptRow {
  id: string;
  meeting_id: string;
  transcript: string;
  timestamp: string;
  audio_start_time: number | null;
  audio_end_time: number | null;
  duration: number | null;
  speaker: SpeakerLabel | null;
}

export interface TranscriptEdit {
  before: TranscriptRow[];
  after: TranscriptRow[];
}

export interface TranscriptMatches {
  segment_ids: string[];
  match_count: number;
}

export type CorrectionCategory = 'name' | 'term' | 'number' | 'word' | 'punctuation';

export interface CorrectionSuggestion {
  segment_id: string;
  original: string;
  suggested: string;
  /** Older servers send none. */
  category?: CorrectionCategory | null;
  reason: string;
}

/** What `suggest_transcript_corrections` returns: suggestions plus lines the server couldn't check. */
export interface ProofreadResult {
  suggestions: CorrectionSuggestion[];
  failed_segment_ids: string[];
}

export const CORRECTION_CATEGORY_LABEL: Record<CorrectionCategory, string> = {
  name: 'Name',
  term: 'Term',
  number: 'Number',
  word: 'Word',
  punctuation: 'Punctuation',
};

/** Adds a retry's suggestions to the ones still under review, in transcript order. */
export function mergeSuggestions(
  existing: CorrectionSuggestion[],
  incoming: CorrectionSuggestion[],
  order: string[],
): CorrectionSuggestion[] {
  const position = new Map(order.map((id, index) => [id, index]));
  const byId = new Map(existing.map((s) => [s.segment_id, s]));
  for (const suggestion of incoming) byId.set(suggestion.segment_id, suggestion);
  return [...byId.values()].sort(
    (a, b) => (position.get(a.segment_id) ?? Infinity) - (position.get(b.segment_id) ?? Infinity),
  );
}

/** The next suggestion after `afterId` in transcript order, wrapping to the first. */
export function nextSuggestionId(suggestionIds: string[], order: string[], afterId: string | null): string | null {
  if (suggestionIds.length === 0) return null;
  const position = new Map(order.map((id, index) => [id, index]));
  const after = afterId === null ? -1 : (position.get(afterId) ?? -1);
  const sorted = [...suggestionIds].sort((a, b) => (position.get(a) ?? Infinity) - (position.get(b) ?? Infinity));
  return sorted.find((id) => (position.get(id) ?? Infinity) > after) ?? sorted[0];
}

/** The note shown while part of a meeting couldn't be proofread, or null. */
export function proofreadCoverageWarning(uncheckedLines: number): string | null {
  if (uncheckedLines === 0) return null;
  return `${uncheckedLines} ${uncheckedLines === 1 ? 'line' : 'lines'} couldn't be checked`;
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

export interface DiffPart {
  kind: 'same' | 'removed' | 'added';
  text: string;
}

/**
 * Word-level changes between a line and its fix, in reading order, so two
 * small fixes in one line show as two small marks, not one struck sentence.
 */
export function diffWords(original: string, suggested: string): DiffPart[] {
  // Whitespace stays a token of its own, so the parts rejoin to the exact lines.
  const a = original.split(/(\s+)/).filter(Boolean);
  const b = suggested.split(/(\s+)/).filter(Boolean);
  const lcs: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const parts: DiffPart[] = [];
  const push = (kind: DiffPart['kind'], text: string) => {
    const last = parts[parts.length - 1];
    if (last?.kind === kind) last.text += text;
    else parts.push({ kind, text });
  };
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      push('same', a[i]);
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      push('removed', a[i++]);
    } else {
      push('added', b[j++]);
    }
  }
  while (i < a.length) push('removed', a[i++]);
  while (j < b.length) push('added', b[j++]);
  return groupChanges(parts);
}

/** One struck phrase and one new phrase per run of changed words ("all water foods" -> "Al Waha Foods"). */
function groupChanges(parts: DiffPart[]): DiffPart[] {
  const grouped: DiffPart[] = [];
  let k = 0;
  while (k < parts.length) {
    if (parts[k].kind === 'same') {
      grouped.push(parts[k++]);
      continue;
    }
    let removed = '';
    let added = '';
    let end = k;
    // A run continues across spaces that sit between two changes.
    while (
      end < parts.length &&
      (parts[end].kind !== 'same' || (/^\s+$/.test(parts[end].text) && parts[end + 1] && parts[end + 1].kind !== 'same'))
    ) {
      const part = parts[end];
      if (part.kind !== 'added') removed += part.text;
      if (part.kind !== 'removed') added += part.text;
      end++;
    }
    if (removed) grouped.push({ kind: 'removed', text: removed });
    if (added) grouped.push({ kind: 'added', text: added });
    k = end;
  }
  return grouped;
}
