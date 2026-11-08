import { describe, expect, test } from 'bun:test';
import {
  EMPTY_HISTORY,
  EMPTY_SELECTION,
  TranscriptEdit,
  TranscriptRow,
  activeSuggestions,
  diffWords,
  mergeSuggestions,
  nextSuggestionId,
  idsBefore,
  popRedo,
  popUndo,
  recordEdit,
  redoOps,
  undoOps,
  updateSelection,
} from '../../src/lib/transcriptEditor';

const row = (id: string, transcript = id): TranscriptRow => ({
  id,
  meeting_id: 'm',
  transcript,
  timestamp: 't',
  audio_start_time: 0,
  audio_end_time: 1,
  duration: 1,
  speaker: null,
});

const order = ['a', 'b', 'c', 'd', 'e'];

describe('updateSelection', () => {
  test('single replaces the selection and sets the anchor', () => {
    const first = updateSelection(EMPTY_SELECTION, order, 'b', 'single');
    const next = updateSelection(first, order, 'd', 'single');
    expect([...next.selected]).toEqual(['d']);
    expect(next.anchor).toBe('d');
  });

  test('range selects from the anchor in either direction', () => {
    const anchored = updateSelection(EMPTY_SELECTION, order, 'c', 'single');
    expect([...updateSelection(anchored, order, 'e', 'range').selected]).toEqual(['c', 'd', 'e']);
    expect([...updateSelection(anchored, order, 'a', 'range').selected]).toEqual(['a', 'b', 'c']);
  });

  test('range keeps its anchor so a later shift-click pivots around it', () => {
    const anchored = updateSelection(EMPTY_SELECTION, order, 'b', 'single');
    const widened = updateSelection(anchored, order, 'e', 'range');
    expect([...updateSelection(widened, order, 'c', 'range').selected]).toEqual(['b', 'c']);
  });

  test('range without an anchor falls back to single', () => {
    expect([...updateSelection(EMPTY_SELECTION, order, 'c', 'range').selected]).toEqual(['c']);
  });

  test('toggle adds and removes one line', () => {
    const on = updateSelection(EMPTY_SELECTION, order, 'b', 'toggle');
    const two = updateSelection(on, order, 'd', 'toggle');
    expect([...two.selected]).toEqual(['b', 'd']);
    expect([...updateSelection(two, order, 'b', 'toggle').selected]).toEqual(['d']);
  });
});

describe('idsBefore', () => {
  test('returns every earlier line', () => {
    expect(idsBefore(order, 'c')).toEqual(['a', 'b']);
  });

  test('is empty for the first line or an unknown id', () => {
    expect(idsBefore(order, 'a')).toEqual([]);
    expect(idsBefore(order, 'zzz')).toEqual([]);
  });
});

describe('undo and redo ops', () => {
  test('undoing a delete restores the rows and removes nothing', () => {
    const edit: TranscriptEdit = { before: [row('a'), row('b')], after: [] };
    expect(undoOps(edit)).toEqual({ deleteIds: [], rows: edit.before });
    expect(redoOps(edit)).toEqual({ deleteIds: ['a', 'b'], rows: [] });
  });

  test('undoing a split removes the new row and restores the original', () => {
    const edit: TranscriptEdit = { before: [row('a', 'Hello there')], after: [row('a', 'Hello'), row('n', 'there')] };
    expect(undoOps(edit)).toEqual({ deleteIds: ['n'], rows: edit.before });
    expect(redoOps(edit)).toEqual({ deleteIds: [], rows: edit.after });
  });

  test('undoing a merge brings back the absorbed rows', () => {
    const edit: TranscriptEdit = { before: [row('a'), row('b')], after: [row('a', 'a b')] };
    expect(undoOps(edit)).toEqual({ deleteIds: [], rows: edit.before });
    expect(redoOps(edit)).toEqual({ deleteIds: ['b'], rows: edit.after });
  });
});

describe('edit history', () => {
  const edit = (id: string): TranscriptEdit => ({ before: [row(id)], after: [] });

  test('undo then redo walks the stack', () => {
    const history = recordEdit(recordEdit(EMPTY_HISTORY, edit('a')), edit('b'));

    const undone = popUndo(history)!;
    expect(undone.edit.before[0].id).toBe('b');
    expect(undone.history.undo).toHaveLength(1);

    const redone = popRedo(undone.history)!;
    expect(redone.edit.before[0].id).toBe('b');
    expect(redone.history.redo).toHaveLength(0);
  });

  test('a new edit clears the redo branch', () => {
    const undone = popUndo(recordEdit(EMPTY_HISTORY, edit('a')))!;
    expect(recordEdit(undone.history, edit('b')).redo).toEqual([]);
  });

  test('popping an empty stack is a no-op', () => {
    expect(popUndo(EMPTY_HISTORY)).toBeNull();
    expect(popRedo(EMPTY_HISTORY)).toBeNull();
  });
});

describe('diffWords', () => {
  const rejoin = (parts: { kind: string; text: string }[], skip: string) =>
    parts.filter((p) => p.kind !== skip).map((p) => p.text).join('');

  test('marks only the misheard word', () => {
    expect(diffWords('Wasool is great', 'Wusool is great')).toEqual([
      { kind: 'removed', text: 'Wasool' },
      { kind: 'added', text: 'Wusool' },
      { kind: 'same', text: ' is great' },
    ]);
  });

  test('keeps two separate fixes separate', () => {
    const parts = diffWords('the a bit dah before the add backs.', 'the EBITDA before the add-backs.');
    expect(parts.filter((p) => p.kind === 'added').map((p) => p.text)).toEqual(['EBITDA', 'add-backs.']);
    expect(parts.some((p) => p.kind === 'same' && p.text.includes('before the'))).toBe(true);
  });

  test('groups a run of changed words into one phrase', () => {
    expect(diffWords('I think all water foods wants it', 'I think Al Waha Foods wants it')).toEqual([
      { kind: 'same', text: 'I think ' },
      { kind: 'removed', text: 'all water foods' },
      { kind: 'added', text: 'Al Waha Foods' },
      { kind: 'same', text: ' wants it' },
    ]);
  });

  test('rejoins to the exact original and suggested lines', () => {
    const original = 'we met  the Acme team today';
    const suggested = 'we met  the ACME team, today';
    const parts = diffWords(original, suggested);
    expect(rejoin(parts, 'added')).toBe(original);
    expect(rejoin(parts, 'removed')).toBe(suggested);
  });
});

describe('activeSuggestions', () => {
  const suggestion = { segment_id: 'a', original: 'Wasool', suggested: 'Wusool', reason: 'name' };

  test('keeps suggestions whose line is unchanged', () => {
    expect(activeSuggestions([suggestion], new Map([['a', 'Wasool']]))).toEqual([suggestion]);
  });

  test('drops suggestions once the line was edited or removed', () => {
    expect(activeSuggestions([suggestion], new Map([['a', 'Wusool']]))).toEqual([]);
    expect(activeSuggestions([suggestion], new Map())).toEqual([]);
  });
});

describe('mergeSuggestions', () => {
  const s = (id: string, suggested = 'x') => ({ segment_id: id, original: 'o', suggested, reason: 'r' });

  test("adds a retry's fixes in transcript order and replaces same-line ones", () => {
    const merged = mergeSuggestions([s('c'), s('a', 'old')], [s('b'), s('a', 'new')], ['a', 'b', 'c']);
    expect(merged.map((m) => [m.segment_id, m.suggested])).toEqual([
      ['a', 'new'],
      ['b', 'x'],
      ['c', 'x'],
    ]);
  });
});

describe('nextSuggestionId', () => {
  const order = ['a', 'b', 'c', 'd', 'e'];

  test('starts at the first fix and steps forward in transcript order', () => {
    expect(nextSuggestionId(['d', 'b'], order, null)).toBe('b');
    expect(nextSuggestionId(['d', 'b'], order, 'b')).toBe('d');
  });

  test('wraps to the first fix after the last', () => {
    expect(nextSuggestionId(['b', 'd'], order, 'd')).toBe('b');
  });

  test('continues from where the accepted fix was', () => {
    // "c" was shown and then accepted, so it is gone from the list.
    expect(nextSuggestionId(['b', 'e'], order, 'c')).toBe('e');
  });

  test('is null with no fixes', () => {
    expect(nextSuggestionId([], order, null)).toBeNull();
  });
});
