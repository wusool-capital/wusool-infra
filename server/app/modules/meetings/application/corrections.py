"""Transcript auto-correct: batches segments, asks the LLM per batch, then
discards any suggestion that doesn't line up with the real transcript.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from app.modules.meetings.application.ports.corrector_llm import CorrectorLLM
from app.modules.meetings.domain.corrections import (
    CorrectionSuggestion,
    TranscriptSegment,
    batch_segments,
)
from app.modules.meetings.domain.prompts import (
    CORRECTION_SYSTEM_PROMPT,
    build_correction_prompt,
)

__all__ = ["CorrectionService"]

_MAX_CONCURRENT_BATCHES = 4
# Low temperature: corrections should be conservative and repeatable.
_TEMPERATURE = 0.0


class CorrectionService:
    def __init__(
        self,
        llm: CorrectorLLM,
        *,
        model_id: str,
        max_tokens: int,
        max_chars_per_batch: int,
    ) -> None:
        self._llm = llm
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._max_chars_per_batch = max_chars_per_batch

    async def suggest(self, segments: Sequence[TranscriptSegment]) -> list[CorrectionSuggestion]:
        batches = batch_segments(segments, max_chars=self._max_chars_per_batch)
        gate = asyncio.Semaphore(_MAX_CONCURRENT_BATCHES)

        async def run(batch: list[TranscriptSegment]) -> list[CorrectionSuggestion]:
            async with gate:
                raw = await self._llm.suggest_corrections(
                    model_id=self._model_id,
                    prompt=build_correction_prompt(batch),
                    system_prompt=CORRECTION_SYSTEM_PROMPT,
                    max_tokens=self._max_tokens,
                    temperature=_TEMPERATURE,
                )
            return _keep_valid(raw, batch)

        results = await asyncio.gather(*(run(batch) for batch in batches))
        return [suggestion for batch_result in results for suggestion in batch_result]


def _keep_valid(
    suggestions: Sequence[CorrectionSuggestion], batch: Sequence[TranscriptSegment]
) -> list[CorrectionSuggestion]:
    """The model can hallucinate ids or paraphrase the original; applying such a
    suggestion client-side would corrupt the wrong segment, so drop it."""
    text_by_id = {segment.segment_id: segment.text for segment in batch}
    seen: set[str] = set()
    kept: list[CorrectionSuggestion] = []
    for suggestion in suggestions:
        actual = text_by_id.get(suggestion.segment_id)
        if actual is None or suggestion.segment_id in seen:
            continue
        if suggestion.original != actual:
            continue
        if not suggestion.suggested.strip() or suggestion.suggested == actual:
            continue
        seen.add(suggestion.segment_id)
        kept.append(suggestion)
    return kept
