import { describe, expect, test } from 'bun:test';
import { levelFraction } from '../../src/hooks/useMicLevel';
import { formatElapsed } from '../../src/lib/formatElapsed';

describe('levelFraction', () => {
  test('silence and loud speech map to the ends of the meter', () => {
    expect(levelFraction(-60)).toBe(0);
    expect(levelFraction(-80)).toBe(0);
    expect(levelFraction(-10)).toBe(1);
    expect(levelFraction(0)).toBe(1);
  });

  test('normal speech lands mid-meter', () => {
    expect(levelFraction(-35)).toBeCloseTo(0.5);
  });
});

describe('formatElapsed', () => {
  test('minutes and seconds under an hour', () => {
    expect(formatElapsed(4)).toBe('0:04');
    expect(formatElapsed(754)).toBe('12:34');
  });

  test('adds hours past sixty minutes', () => {
    expect(formatElapsed(4512)).toBe('1:15:12');
  });
});
