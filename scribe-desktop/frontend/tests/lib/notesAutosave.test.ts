import { describe, expect, test } from 'bun:test';
import { createAutosave, NOTES_TOO_LONG, type NotesSaveState } from '../../src/lib/notesAutosave';

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('createAutosave', () => {
  test('writes only the latest value after the debounce', async () => {
    const saved: string[] = [];
    const states: NotesSaveState[] = [];
    const autosave = createAutosave<string>(async (v) => void saved.push(v), (s) => states.push(s), 10);

    autosave.schedule('a');
    autosave.schedule('ab');
    await wait(30);

    expect(saved).toEqual(['ab']);
    expect(states.at(-1)).toBe('saved');
  });

  test('flush writes immediately and cancels the timer', async () => {
    const saved: string[] = [];
    const autosave = createAutosave<string>(async (v) => void saved.push(v), () => {}, 1000);

    autosave.schedule('x');
    await autosave.flush();
    await wait(5);

    expect(saved).toEqual(['x']);
  });

  test('a failed save reports error', async () => {
    const states: NotesSaveState[] = [];
    const autosave = createAutosave<string>(
      async () => {
        throw new Error('disk full');
      },
      (s) => states.push(s),
      1,
    );

    autosave.schedule('x');
    await autosave.flush();

    expect(states.at(-1)).toBe('error');
  });

  test('the length cap reports too_long', async () => {
    const states: NotesSaveState[] = [];
    const autosave = createAutosave<string>(
      async () => {
        throw NOTES_TOO_LONG;
      },
      (s) => states.push(s),
      1,
    );

    autosave.schedule('x');
    await autosave.flush();

    expect(states.at(-1)).toBe('too_long');
  });

  test('cancel drops a pending save', async () => {
    const saved: string[] = [];
    const autosave = createAutosave<string>(async (v) => void saved.push(v), () => {}, 5);

    autosave.schedule('x');
    autosave.cancel();
    await wait(15);

    expect(saved).toEqual([]);
  });
});
