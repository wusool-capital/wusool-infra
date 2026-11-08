import { describe, expect, test } from 'bun:test';
import {
  MAX_VOCABULARY_WORDS,
  MAX_VOCABULARY_WORD_LENGTH,
  addVocabularyWords,
  removeVocabularyWord,
} from '../../src/lib/proofreadVocabulary';
import { proofreadCoverageWarning } from '../../src/lib/transcriptEditor';

describe('addVocabularyWords', () => {
  test('splits pasted lists and trims each word', () => {
    expect(addVocabularyWords([], ' Project  Falcon, Tamkeen\nGulf Horizon ,, ')).toEqual([
      'Project Falcon',
      'Tamkeen',
      'Gulf Horizon',
    ]);
  });

  test('skips words already in the list, ignoring case', () => {
    expect(addVocabularyWords(['Tamkeen'], 'tamkeen, TAMKEEN, Falcon')).toEqual(['Tamkeen', 'Falcon']);
  });

  test('caps word length and list size', () => {
    expect(addVocabularyWords([], 'x'.repeat(120))[0]).toHaveLength(MAX_VOCABULARY_WORD_LENGTH);
    const full = Array.from({ length: MAX_VOCABULARY_WORDS }, (_, i) => `w${i}`);
    expect(addVocabularyWords(full, 'one more')).toHaveLength(MAX_VOCABULARY_WORDS);
  });
});

test('removeVocabularyWord drops only that word', () => {
  expect(removeVocabularyWord(['a', 'b', 'c'], 'b')).toEqual(['a', 'c']);
});

describe('proofreadCoverageWarning', () => {
  test('is null when every line was checked', () => {
    expect(proofreadCoverageWarning({ suggestions: [], failed_segment_ids: [] })).toBeNull();
  });

  test('counts the lines that were not checked', () => {
    expect(proofreadCoverageWarning({ suggestions: [], failed_segment_ids: ['a'] })).toBe(
      "1 line couldn't be checked. Try Proofread again.",
    );
    expect(proofreadCoverageWarning({ suggestions: [], failed_segment_ids: ['a', 'b'] })).toBe(
      "2 lines couldn't be checked. Try Proofread again.",
    );
  });
});
