"""Transcript auto-correct: batches segments, asks the LLM per batch, then
discards any suggestion that doesn't line up with the real transcript.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import replace

from app.modules.meetings.application.ports.corrector_llm import CorrectorLLM
from app.modules.meetings.domain.corrections import (
    CorrectionSuggestion,
    TranscriptSegment,
    batch_segments,
)
from app.modules.meetings.domain.prompts import (
    CORRECTION_SYSTEM_PROMPT,
    build_correction_prompt,
    sanitize_segment_text,
)

__all__ = ["CorrectionService"]

logger = logging.getLogger(__name__)

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
        gate: asyncio.Semaphore,
    ) -> None:
        # Process-wide so concurrent requests can't multiply Bedrock load.
        self._gate = gate
        self._llm = llm
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._max_chars_per_batch = max_chars_per_batch

    async def suggest(self, segments: Sequence[TranscriptSegment]) -> list[CorrectionSuggestion]:
        batches = batch_segments(segments, max_chars=self._max_chars_per_batch)

        async def run(batch: list[TranscriptSegment]) -> list[CorrectionSuggestion]:
            async with self._gate:
                raw = await self._llm.suggest_corrections(
                    model_id=self._model_id,
                    prompt=build_correction_prompt(batch),
                    system_prompt=CORRECTION_SYSTEM_PROMPT,
                    max_tokens=self._max_tokens,
                    temperature=_TEMPERATURE,
                )
            return _keep_valid(raw, batch)

        results = await asyncio.gather(*(run(batch) for batch in batches), return_exceptions=True)
        failures = [r for r in results if isinstance(r, BaseException)]
        # A partial result is still useful; only fail when nothing came back.
        if failures and len(failures) == len(results):
            raise failures[0]
        for failure in failures:
            logger.warning("Correction batch failed: %s", failure)
        return [
            suggestion
            for batch_result in results
            if not isinstance(batch_result, BaseException)
            for suggestion in batch_result
        ]


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
        # The model only saw delimiter-stripped text, so match against that.
        if suggestion.original not in (actual, sanitize_segment_text(actual)):
            continue
        if not suggestion.suggested.strip() or suggestion.suggested == actual:
            continue
        seen.add(suggestion.segment_id)
        # Clients match on the stored text, so report that, not the stripped copy.
        kept.append(replace(suggestion, original=actual))
    return kept
