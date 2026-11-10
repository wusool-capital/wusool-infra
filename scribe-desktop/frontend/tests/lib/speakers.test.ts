import { describe, expect, test } from 'bun:test';
import { MeetingSpeaker, diarizedIndex, formatTalkTime, mergeTarget, separationProgress, speakerDisplayName, summaryLine } from '../../src/lib/speakers';

const speakers: MeetingSpeaker[] = [
  { label: 'speaker_0', profile_id: 'p-1', name: 'Alice' },
  { label: 'speaker_1', profile_id: null, name: null },
];

describe('speakerDisplayName', () => {
  test('uses the named person for a diarized voice', () => {
    expect(speakerDisplayName('speaker_0', speakers, null)).toBe('Alice');
  });

  test('falls back to a 1-based placeholder for unnamed voices', () => {
    expect(speakerDisplayName('speaker_1', speakers, null)).toBe('Speaker 2');
    expect(speakerDisplayName('speaker_4', speakers, null)).toBe('Speaker 5');
  });

  test('shows the local user by their own name when set', () => {
    expect(speakerDisplayName('me', speakers, 'Sam')).toBe('Sam');
    expect(speakerDisplayName('me', speakers, null)).toBe('Me');
  });

  test('labels undiarized meeting audio and legacy rows', () => {
    expect(speakerDisplayName('others', speakers, null)).toBe('Others');
    expect(speakerDisplayName(null, speakers, null)).toBeNull();
  });
});

describe('diarizedIndex', () => {
  test('only diarized labels have an index', () => {
    expect(diarizedIndex('speaker_3')).toBe(3);
    expect(diarizedIndex('me')).toBeNull();
    expect(diarizedIndex('others')).toBeNull();
  });
});

describe('formatTalkTime', () => {
  test('reads at a glance from seconds to hours', () => {
    expect(formatTalkTime(44.6)).toBe('45 s');
    expect(formatTalkTime(840)).toBe('14 min');
    expect(formatTalkTime(3600)).toBe('1 h');
    expect(formatTalkTime(3900)).toBe('1 h 5 min');
  });
});

describe('separationProgress', () => {
  const run = { started_at_ms: 1_000_000, estimated_seconds: 100 };

  test('has no estimate while queued', () => {
    expect(separationProgress({ started_at_ms: null, estimated_seconds: null }, 1_000_000)).toBeNull();
  });

  test('tracks elapsed time against the estimate', () => {
    expect(separationProgress(run, 1_000_000 + 25_000)).toEqual({ percent: 25, secondsLeft: 75 });
  });

  test('holds short of full when the run outlasts its estimate', () => {
    expect(separationProgress(run, 1_000_000 + 500_000)).toEqual({ percent: 95, secondsLeft: 0 });
  });
});

describe('mergeTarget', () => {
  const speakers: MeetingSpeaker[] = [
    { label: 'speaker_0', profile_id: 'p-1', name: 'Saleeq' },
    { label: 'speaker_1', profile_id: null, name: null },
  ];

  test('finds another voice already named that, in any case', () => {
    expect(mergeTarget('speaker_1', '  saleeq ', speakers)).toBe('Saleeq');
  });

  test('ignores the voice being named and new names', () => {
    expect(mergeTarget('speaker_0', 'Saleeq', speakers)).toBeNull();
    expect(mergeTarget('speaker_1', 'Oliver', speakers)).toBeNull();
    expect(mergeTarget('speaker_1', '   ', speakers)).toBeNull();
  });
});

describe('mergeTarget case folding', () => {
  test('folds only A-Z, like SQLite NOCASE, so it never promises a merge the database will not make', () => {
    const speakers: MeetingSpeaker[] = [{ label: 'speaker_0', profile_id: 'p-1', name: 'Émile' }];
    expect(mergeTarget('speaker_1', 'émile', speakers)).toBeNull();
    expect(mergeTarget('speaker_1', 'ÉMILE', speakers)).toBe('Émile');
  });
});

describe('summaryLine', () => {
  const speakers: MeetingSpeaker[] = [{ label: 'speaker_0', profile_id: 'p-1', name: 'Saleeq' }];
  const nameOf = (label: Parameters<typeof speakerDisplayName>[0]) => speakerDisplayName(label, speakers, 'Sinan');

  test('puts the speaker between the time and the words', () => {
    expect(summaryLine('[01:05]', "I'll ship it Friday.", nameOf('speaker_0'))).toBe("[01:05] Saleeq: I'll ship it Friday.");
    expect(summaryLine('[01:07]', 'Sounds good.', nameOf('me'))).toBe('[01:07] Sinan: Sounds good.');
  });

  test('unnamed voices read as Speaker N, and lines without a speaker stay as they were', () => {
    expect(summaryLine('[02:00]', 'Agreed.', nameOf('speaker_2'))).toBe('[02:00] Speaker 3: Agreed.');
    expect(summaryLine('[02:01]', 'Hello.', nameOf(null))).toBe('[02:01] Hello.');
  });
});
