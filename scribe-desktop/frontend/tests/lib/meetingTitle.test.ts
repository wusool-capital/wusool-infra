import { expect, test } from 'bun:test';
import { defaultMeetingTitle } from '../../src/lib/meetingTitle';

test('default meeting title is readable and matches the Rust format', () => {
  expect(defaultMeetingTitle(new Date(2026, 10, 7, 8, 5, 9))).toBe('Meeting · 7 Nov, 08:05');
});
