// Mirrors the server's caps (POST /desktop/transcripts/corrections), so nothing typed here is rejected there.
export const MAX_VOCABULARY_WORDS = 200;
export const MAX_VOCABULARY_WORD_LENGTH = 80;

/** Adds what the user typed or pasted: comma or newline separated, trimmed, no repeats (ignoring case). */
export function addVocabularyWords(existing: string[], input: string): string[] {
  const seen = new Set(existing.map((word) => word.toLowerCase()));
  const added: string[] = [];
  for (const raw of input.split(/[,\n]/)) {
    const word = raw.replace(/\s+/g, ' ').trim().slice(0, MAX_VOCABULARY_WORD_LENGTH);
    if (!word || seen.has(word.toLowerCase())) continue;
    seen.add(word.toLowerCase());
    added.push(word);
  }
  return [...existing, ...added].slice(0, MAX_VOCABULARY_WORDS);
}

export function removeVocabularyWord(existing: string[], word: string): string[] {
  return existing.filter((entry) => entry !== word);
}
