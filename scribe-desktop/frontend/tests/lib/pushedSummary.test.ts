import { describe, expect, test } from 'bun:test';
import {
  hasDealSignal,
  parsePushedSummary,
  splitLead,
  splitOwner,
  summaryToPlainText,
} from '../../src/lib/pushedSummary';

const dealSummary = {
  title: '[Seller: Al Waha Foods] Floor price call',
  executive_summary: 'Floor agreed at AED 42m. Two add-backs need documents.',
  notes: [
    { topic: 'Valuation', points: ['7x adjusted EBITDA of AED 6m.'] },
    { topic: 'Empty', points: [] },
  ],
  decisions: ['Floor of AED 42m.'],
  action_items: ['Sinan: send the request, by 12 Nov 2026.'],
  claims_to_verify: ['AED 1.1m add-back: no payroll record.'],
  risks: ['Carrefour is 35% of revenue.'],
  deal_momentum: 'Advanced — floor agreed.',
  keywords: ['floor price'],
};

describe('summaryToPlainText', () => {
  test('follows the new order and groups the deal signal', () => {
    expect(summaryToPlainText(dealSummary)).toBe(
      [
        'Floor agreed at AED 42m. Two add-backs need documents.',
        'Next steps\n- Sinan: send the request, by 12 Nov 2026.',
        'Decisions\n- Floor of AED 42m.',
        'Deal signal\nMomentum: Advanced — floor agreed.\nTo verify\n- AED 1.1m add-back: no payroll record.\nRisks\n- Carrefour is 35% of revenue.',
        'Notes\n\nValuation\n- 7x adjusted EBITDA of AED 6m.',
      ].join('\n\n'),
    );
  });

  test('shows plain risks for a meeting with no deal signal', () => {
    const text = summaryToPlainText({ executive_summary: 'Gist.', risks: ['Blocked on Wing.'], deal_momentum: '' });
    expect(text).toBe('Gist.\n\nRisks\n- Blocked on Wing.');
  });

  test('keeps an older summary readable', () => {
    const text = summaryToPlainText({
      executive_summary: 'First paragraph.\n\nSecond paragraph.',
      action_items: ['Do it'],
      discussion_topics: ['Pricing'],
      open_questions: ['Who signs?'],
    });
    expect(text).toBe(
      'First paragraph.\n\nSecond paragraph.\n\nNext steps\n- Do it\n\nDiscussion Topics\n- Pricing\n\nOpen Questions\n- Who signs?',
    );
  });
});

describe('parsePushedSummary', () => {
  test('ignores malformed fields', () => {
    const parsed = parsePushedSummary({ executive_summary: 5, notes: ['x', null, { topic: 'T', points: 'no' }], risks: 'r' });
    expect(parsed.gist).toEqual([]);
    expect(parsed.notes).toEqual([]);
    expect(parsed.risks).toEqual([]);
    expect(hasDealSignal(parsed)).toBe(false);
  });
});

describe('splitOwner', () => {
  test('separates a leading owner', () => {
    expect(splitOwner('Sinan: send the request')).toEqual({ owner: 'Sinan', action: 'send the request' });
  });

  test('leaves an item without an owner whole', () => {
    expect(splitOwner('Revisit the floor once the audit lands')).toEqual({
      owner: null,
      action: 'Revisit the floor once the audit lands',
    });
  });
});

describe('splitLead', () => {
  test('splits off the first sentence', () => {
    expect(splitLead('Floor agreed at $3.5M. It resets on audit.')).toEqual({
      lead: 'Floor agreed at $3.5M.',
      rest: 'It resets on audit.',
    });
  });

  test('does not end the lead at an abbreviation', () => {
    expect(splitLead('U.S. buyer Acme agreed the floor. Diligence starts Monday.')).toEqual({
      lead: 'U.S. buyer Acme agreed the floor.',
      rest: 'Diligence starts Monday.',
    });
    expect(splitLead('Dr. Smith of Nomad Retail Co. confirmed the range. Next call 26 Nov.').lead).toBe(
      'Dr. Smith of Nomad Retail Co. confirmed the range.',
    );
  });

  test('keeps a single sentence whole', () => {
    expect(splitLead('Only one sentence.')).toEqual({ lead: 'Only one sentence.', rest: '' });
  });
});
