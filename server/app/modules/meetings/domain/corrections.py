"""Value objects for transcript proofread (speech-to-text fixes only)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Literal

__all__ = [
    "CorrectionCategory",
    "CorrectionContext",
    "CorrectionEdit",
    "CorrectionResult",
    "CorrectionSuggestion",
    "TranscriptSegment",
    "batch_segments",
    "is_minor_edit",
    "keep_sound_alike_changes",
    "relevant_terms",
    "sounds_alike",
]

CorrectionCategory = Literal["name", "term", "number", "word", "punctuation"]

# A mishearing spans a few words ("a bit dah" -> "EBITDA"); more is a rewrite.
_MAX_CHANGED_WORDS = 3
_MAX_CHANGED_SHARE = 0.4
_ARABIC = re.compile("[\u0600-\u06ff]")
# Below this, the heard words and the fix don't sound alike: a different word, not a mishearing.
_MIN_SOUND_SIMILARITY = 0.5
# A spelling-list word joins a batch's prompt only if something said there sounds this close.
_MIN_TERM_SIMILARITY = 0.6
_MAX_WINDOW_WORDS = 3


@dataclass(frozen=True)
class TranscriptSegment:
    segment_id: str
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class CorrectionContext:
    """What the meeting is about, so the model knows the names it should hear."""

    title: str | None = None
    names: tuple[str, ...] = ()
    vocabulary: tuple[str, ...] = ()


@dataclass(frozen=True)
class CorrectionEdit:
    """One fix as the model returns it, against a batch-local line number."""

    line: int
    suggested: str
    category: CorrectionCategory
    reason: str


@dataclass(frozen=True)
class CorrectionSuggestion:
    segment_id: str
    original: str
    suggested: str
    category: CorrectionCategory
    reason: str


@dataclass(frozen=True)
class CorrectionResult:
    suggestions: list[CorrectionSuggestion]
    checked_segments: int
    # Lines whose batch errored, so the client can say they were not checked.
    failed_segment_ids: list[str] = field(default_factory=list)


def batch_segments(
    segments: Sequence[TranscriptSegment], *, max_chars: int
) -> list[list[TranscriptSegment]]:
    """Greedy batches by total text length; an oversized segment gets its own batch."""
    batches: list[list[TranscriptSegment]] = []
    current: list[TranscriptSegment] = []
    current_chars = 0
    for segment in segments:
        size = len(segment.text)
        if current and current_chars + size > max_chars:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += size
    if current:
        batches.append(current)
    return batches


def _words(text: str, *, keep_case: bool = False) -> list[str]:
    """Words without punctuation, lower-cased unless asked, with letters spoken
    one at a time joined ("C I C D" -> "cicd"), so an acronym counts as one word."""
    words: list[str] = []
    letters = ""
    for raw in (text if keep_case else text.lower()).split():
        word = re.sub(r"[^\w]", "", raw)
        if len(word) == 1 and word.isalpha():
            letters += word
            continue
        if letters:
            words.append(letters)
            letters = ""
        if word:
            words.append(word)
    if letters:
        words.append(letters)
    return words


def is_minor_edit(original: str, suggested: str) -> bool:
    """A transcription fix changes a few words; anything bigger is a rewrite,
    and a switch between Arabic and Latin script is a translation."""
    if bool(_ARABIC.search(original)) != bool(_ARABIC.search(suggested)):
        return False
    before, after = _words(original), _words(suggested)
    changed = sum(
        max(i2 - i1, j2 - j1)
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, before, after).get_opcodes()
        if tag != "equal"
    )
    return changed <= max(_MAX_CHANGED_WORDS, _MAX_CHANGED_SHARE * len(before))


def _sound_key(text: str) -> str:
    """A rough spelling-independent key: c/k/q and s/z alike, ph as f, no doubled letters."""
    key = text.lower().replace("ph", "f").replace("ck", "k")
    key = key.translate(str.maketrans({"c": "k", "q": "k", "z": "s"}))
    return re.sub(r"(.)\1+", r"\1", key)


def _is_acronym(word: str) -> bool:
    return 2 <= len(word) <= 6 and sum(ch.isupper() for ch in word) >= 2


def sounds_alike(original: str, suggested: str) -> bool:
    """Every replaced span must sound like what was heard ("locum" -> "Lokam"),
    never swap in an unrelated word or name ("Anerey" -> "Raoof"). Added or
    dropped words are not mishearings. Acronyms are exempt: spoken letters
    ("sea I am" -> "CIM") don't spell like the result.
    """
    before = _words(original)
    after_cased = _words(suggested, keep_case=True)
    after = [word.lower() for word in after_cased]
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, before, after).get_opcodes():
        if tag == "equal":
            continue
        if tag != "replace":
            return False
        if all(_is_acronym(word) for word in after_cased[j1:j2]):
            continue
        heard = _sound_key("".join(before[i1:i2]))
        fixed = _sound_key("".join(after[j1:j2]))
        if SequenceMatcher(None, heard, fixed).ratio() < _MIN_SOUND_SIMILARITY:
            return False
    return True


def relevant_terms(terms: Sequence[str], texts: Sequence[str]) -> tuple[str, ...]:
    """The user's words that sound like something said in `texts`.

    A word the model sees, it tries to use: given "Raoof" it renamed
    unrelated people to Raoof. So a batch only gets the words that could be
    misheard in it. Acronyms always go, since spoken letters don't spell like
    them. Starting with the same sound is required, which keeps this cheap.
    """
    windows: dict[str, set[str]] = {}
    for text in texts:
        words = _words(text)
        for size in range(1, _MAX_WINDOW_WORDS + 1):
            for start in range(len(words) - size + 1):
                key = _sound_key("".join(words[start : start + size]))
                windows.setdefault(key[:1], set()).add(key)
    kept: list[str] = []
    for term in terms:
        if _is_acronym(re.sub(r"[^\w]", "", term)):
            kept.append(term)
            continue
        target = _sound_key("".join(_words(term)))
        candidates = windows.get(target[:1], ())
        if any(
            SequenceMatcher(None, target, candidate).ratio() >= _MIN_TERM_SIMILARITY
            for candidate in candidates
            if abs(len(candidate) - len(target)) <= max(2, len(target) // 2)
        ):
            kept.append(term)
    return tuple(kept)


def _change_runs(before: list[str], after: list[str]) -> list[tuple[int, int, int, int]]:
    """Changed token ranges, with runs split only by spaces merged into one."""
    runs: list[list[int]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        gap = before[runs[-1][1] : i1] if runs else None
        if runs and gap is not None and all(not token.strip() for token in gap):
            runs[-1][1], runs[-1][3] = i2, j2
        else:
            runs.append([i1, i2, j1, j2])
    return [(i1, i2, j1, j2) for i1, i2, j1, j2 in runs]


def keep_sound_alike_changes(original: str, suggested: str) -> str:
    """The fix with every change that doesn't sound like what was heard put
    back, so one bad name swap doesn't throw away a good fix on the same line."""
    before = re.split(r"(\s+)", original)
    after = re.split(r"(\s+)", suggested)
    kept: list[str] = []
    cursor = 0
    for i1, i2, j1, j2 in _change_runs(before, after):
        kept.extend(before[cursor:i1])
        heard, fixed = "".join(before[i1:i2]), "".join(after[j1:j2])
        kept.append(
            fixed if heard.strip() and fixed.strip() and sounds_alike(heard, fixed) else heard
        )
        cursor = i2
    kept.extend(before[cursor:])
    return "".join(kept)
