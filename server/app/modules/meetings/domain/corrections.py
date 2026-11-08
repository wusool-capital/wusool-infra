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
]

CorrectionCategory = Literal["name", "term", "number", "word", "punctuation"]

# A mishearing spans a few words ("a bit dah" -> "EBITDA"); more is a rewrite.
_MAX_CHANGED_WORDS = 3
_MAX_CHANGED_SHARE = 0.4
_ARABIC = re.compile("[\u0600-\u06ff]")


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


def _words(text: str) -> list[str]:
    """Lower-cased words without punctuation, with letters spoken one at a
    time joined ("C I C D" -> "cicd"), so joining an acronym counts as one change."""
    words: list[str] = []
    letters = ""
    for raw in text.lower().split():
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
