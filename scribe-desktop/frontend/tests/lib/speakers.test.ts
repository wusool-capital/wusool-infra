import { describe, expect, test } from 'bun:test';
import { MeetingSpeaker, diarizedIndex, formatTalkTime, speakerDisplayName } from '../../src/lib/speakers';

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
