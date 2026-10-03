"""Value objects for transcript auto-correct (speech-to-text fixes only)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

__all__ = ["CorrectionSuggestion", "TranscriptSegment", "batch_segments"]


@dataclass(frozen=True)
class TranscriptSegment:
    segment_id: str
    text: str


@dataclass(frozen=True)
class CorrectionSuggestion:
    segment_id: str
    original: str
    suggested: str
    reason: str


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
