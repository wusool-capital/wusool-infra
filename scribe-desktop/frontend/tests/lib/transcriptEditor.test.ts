import { describe, expect, test } from 'bun:test';
import {
  EMPTY_HISTORY,
  EMPTY_SELECTION,
  TranscriptEdit,
  TranscriptRow,
  activeSuggestions,
  diffSpan,
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

describe('diffSpan', () => {
  test('isolates a misheard word', () => {
    expect(diffSpan('Wasool is great', 'Wusool is great')).toEqual({
      prefix: '',
      removed: 'Wasool',
      added: 'Wusool',
      suffix: ' is great',
    });
  });

  test('keeps surrounding words in the prefix and suffix', () => {
    const span = diffSpan('we met the Acme team today', 'we met the ACME team today');
    expect(span.prefix).toBe('we met the ');
    expect(span.removed).toBe('Acme');
    expect(span.added).toBe('ACME');
    expect(span.suffix).toBe(' team today');
  });

  test('handles a change at the end of the line', () => {
    const span = diffSpan('that is right', 'that is right.');
    expect(span.removed).toBe('right');
    expect(span.added).toBe('right.');
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
