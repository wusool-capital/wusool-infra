"""Transcript proofread: batches segments, asks the LLM per batch, then
discards any suggestion that doesn't line up with the real transcript.

Each batch numbers its lines 1..n, so the model never echoes long segment
ids or the original text; the server maps line numbers back and reports the
stored text as `original`, which the desktop uses to check the line hasn't
changed before applying a fix. The two lines before each batch go along as
read-only context, so a batch's first line keeps the sentence it continues.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

from app.modules.meetings.application.ports.corrector_llm import CorrectorLLM
from app.modules.meetings.domain.corrections import (
    CorrectionContext,
    CorrectionEdit,
    CorrectionResult,
    CorrectionSuggestion,
    TranscriptSegment,
    batch_segments,
    is_minor_edit,
    keep_sound_alike_changes,
    relevant_terms,
)
from app.modules.meetings.domain.prompts import (
    CORRECTION_SYSTEM_PROMPT,
    build_correction_prompt,
    sanitize_segment_text,
)
from app.modules.meetings.domain.vocabulary import COMMON_NAMES

__all__ = ["CorrectionService"]

logger = logging.getLogger(__name__)

# Low temperature: corrections should be conservative and repeatable.
_TEMPERATURE = 0.0
_CONTEXT_LINES = 2


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

    async def suggest(
        self,
        segments: Sequence[TranscriptSegment],
        context: CorrectionContext | None = None,
    ) -> CorrectionResult:
        batches = batch_segments(segments, max_chars=self._max_chars_per_batch)
        dropped: Counter[str] = Counter()

        async def run(index: int) -> list[CorrectionSuggestion]:
            batch = batches[index]
            previous = batches[index - 1][-_CONTEXT_LINES:] if index else []
            prompt = build_correction_prompt(
                batch, previous=previous, context=_for_batch(context, [*previous, *batch])
            )
            async with self._gate:
                edits = await self._llm.suggest_corrections(
                    model_id=self._model_id,
                    prompt=prompt,
                    system_prompt=CORRECTION_SYSTEM_PROMPT,
                    max_tokens=self._max_tokens,
                    temperature=_TEMPERATURE,
                )
            return _keep_valid(edits, batch, dropped)

        results = await asyncio.gather(
            *(run(i) for i in range(len(batches))), return_exceptions=True
        )
        failed = [
            batch for batch, r in zip(batches, results, strict=True) if isinstance(r, BaseException)
        ]
        # A partial result is still useful; only fail when nothing came back.
        if failed and len(failed) == len(batches):
            first = next(r for r in results if isinstance(r, BaseException))
            raise first
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("correction_batch_failed error=%s", type(result).__name__)

        suggestions = [s for r in results if not isinstance(r, BaseException) for s in r]
        failed_ids = [segment.segment_id for batch in failed for segment in batch]
        logger.info(
            "corrections_suggested segments=%d batches=%d failed_batches=%d kept=%d dropped=%s",
            len(segments),
            len(batches),
            len(failed),
            len(suggestions),
            dict(dropped),
            extra={
                "segments": len(segments),
                "batches": len(batches),
                "failed_batches": len(failed),
                "kept": len(suggestions),
                "dropped": dict(dropped),
            },
        )
        return CorrectionResult(
            suggestions=suggestions,
            checked_segments=len(segments) - len(failed_ids),
            failed_segment_ids=failed_ids,
        )


def _for_batch(
    context: CorrectionContext | None, segments: Sequence[TranscriptSegment]
) -> CorrectionContext:
    """Only the names and words that something in this batch sounds like:
    the model renamed strangers to whichever name it was shown."""
    texts = [segment.text for segment in segments]
    context = context or CorrectionContext()
    return replace(
        context,
        names=relevant_terms(context.names, texts),
        vocabulary=relevant_terms(context.vocabulary, texts),
        common_names=relevant_terms(COMMON_NAMES, texts),
    )


def _keep_valid(
    edits: Sequence[CorrectionEdit],
    batch: Sequence[TranscriptSegment],
    dropped: Counter[str],
) -> list[CorrectionSuggestion]:
    """Applying a bad suggestion client-side corrupts the transcript, so drop
    anything that isn't a small fix to a real, editable line."""
    seen: set[int] = set()
    kept: list[CorrectionSuggestion] = []
    for edit in edits:
        if not 1 <= edit.line <= len(batch):
            dropped["unknown_line"] += 1
            continue
        if edit.line in seen:
            dropped["duplicate"] += 1
            continue
        segment = batch[edit.line - 1]
        # The model saw this line with our prompt markers stripped; its fix would delete them.
        if sanitize_segment_text(segment.text) != segment.text:
            dropped["prompt_marker"] += 1
            continue
        suggested = edit.suggested.strip()
        if not suggested or suggested == segment.text.strip():
            dropped["no_change"] += 1
            continue
        if not is_minor_edit(segment.text, suggested):
            dropped["rewrite"] += 1
            continue
        # Changes that don't sound like what was heard are put back, not just dropped,
        # so a bad name swap doesn't sink a good fix on the same line.
        kept_text = keep_sound_alike_changes(segment.text, suggested)
        if kept_text.strip() == segment.text.strip():
            dropped["not_sound_alike"] += 1
            continue
        if kept_text != suggested:
            dropped["partly_reverted"] += 1
        suggested = kept_text
        seen.add(edit.line)
        kept.append(
            CorrectionSuggestion(
                segment_id=segment.segment_id,
                original=segment.text,
                suggested=suggested,
                category=edit.category,
                reason=edit.reason,
            )
        )
    return kept
