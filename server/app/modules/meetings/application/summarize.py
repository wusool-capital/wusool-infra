"""Standalone collaborator, not a `ServiceBase` mixin — nothing outside
`PublishMixin` calls this directly, exactly how `matching_engine`'s
`MatchReasoningService` sits outside its own mixin facade (see
`application/base.py`'s docstring there).

Ported from Scribe's `app.ai.summarizer.HierarchicalSummarizer`. The
`SummarizerLLM` port returns validated `MeetingSummary` objects, so this
module only orchestrates the single-pass or map-reduce calls.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import asdict, replace

from app.modules.meetings.application.ports.summarizer_llm import SummarizerLLM
from app.modules.meetings.domain.chunking import chunk_text
from app.modules.meetings.domain.prompts import (
    SYSTEM_PROMPT,
    build_chunk_summary_prompt,
    build_merge_prompt,
    build_single_pass_summary_prompt,
    summary_budget,
)
from app.modules.meetings.domain.roles import MeetingRole, momentum_applies
from app.modules.meetings.domain.summary import MeetingSummary

__all__ = ["SummarizationService"]

# Below this many words there's no real signal to summarize — an empty or
# near-empty transcript (a call that never actually started, a few seconds
# of dead air) gives the model nothing to work with, and asking it to
# summarize "nothing" produces exactly the kind of filler prose that
# describes its own absence of input rather than a meeting. Skipping the
# LLM call entirely also means no risk of it echoing internal prompt
# scaffolding (delimiter markers, etc.) back into a user-facing summary.
_MIN_TRANSCRIPT_WORDS = 20

_NO_CONTENT_SUMMARY = MeetingSummary(
    title="No meeting content to summarise",
    executive_summary=(
        "The recording didn't capture enough speech to summarise: the "
        "transcript was empty or too short."
    ),
)


def _without_stray_momentum(
    summary: MeetingSummary, companies: Mapping[MeetingRole, str] | None
) -> MeetingSummary:
    """Bedrock's forced schema makes the model fill deal_momentum even for
    internal meetings ("N/A — internal update"), which would show a deal
    signal on a meeting with no counterparty.
    """
    if not summary.deal_momentum or (companies and momentum_applies(companies)):
        return summary
    return replace(summary, deal_momentum="")


class SummarizationService:
    def __init__(
        self,
        llm: SummarizerLLM,
        *,
        model_id: str,
        summary_max_tokens: int,
        summary_max_tokens_per_chunk: int,
    ) -> None:
        self._llm = llm
        self._model_id = model_id
        self._summary_max_tokens = summary_max_tokens
        self._summary_max_tokens_per_chunk = summary_max_tokens_per_chunk

    async def summarize(
        self,
        transcript_text: str,
        *,
        companies: Mapping[MeetingRole, str] | None,
        meeting_date: str | None,
    ) -> MeetingSummary:
        """Summarize *transcript_text*.

        *companies* is {role: company_name} for whatever this meeting's
        tagged companies are, and *meeting_date* is the meeting's own date
        — both are passed through as delimited prompt context so the model
        can prefix the title, attribute points by role rather than by
        unreliable speaker label, resolve relative deadlines into absolute
        dates, and (only when an external counterparty role is present)
        judge deal_momentum. Neither is ever treated as part of the
        transcript.
        """
        transcript_words = len(transcript_text.split())
        if transcript_words < _MIN_TRANSCRIPT_WORDS:
            return _NO_CONTENT_SUMMARY
        # Sized from the whole transcript, so a long meeting's merge step gets the long budget.
        budget = summary_budget(transcript_words)

        chunks = chunk_text(
            transcript_text, max_tokens_per_chunk=self._summary_max_tokens_per_chunk
        )

        if len(chunks) <= 1:
            single = chunks[0] if chunks else ""
            summary = await self._call_llm(
                build_single_pass_summary_prompt(
                    single, budget=budget, companies=companies, meeting_date=meeting_date
                ),
                check_limits=True,
            )
            return _without_stray_momentum(summary, companies)

        # MAP: one summarize() call per chunk. Run concurrently — unlike
        # Scribe, which does this serially — since nothing here forbids
        # it and Scribe's own comments flag it as an easy win; the REDUCE
        # step below still waits on all of them anyway.
        chunk_summaries = await asyncio.gather(
            *(
                self._call_llm(
                    build_chunk_summary_prompt(
                        chunk, companies=companies, meeting_date=meeting_date
                    ),
                    check_limits=False,
                )
                for chunk in chunks
            )
        )

        # REDUCE: same output-token budget as every other call here (see
        # _call_llm) — the map step's prompt asks it to favor completeness
        # over brevity and preserve every figure verbatim, which a smaller
        # budget would quietly work against.
        merged = await self._call_llm(
            build_merge_prompt(
                [json.dumps(asdict(summary)) for summary in chunk_summaries],
                budget=budget,
                companies=companies,
                meeting_date=meeting_date,
            ),
            check_limits=True,
        )
        return _without_stray_momentum(merged, companies)

    async def _call_llm(self, prompt: str, *, check_limits: bool) -> MeetingSummary:
        # temperature=0.0 always: summarization wants the same deterministic-
        # leaning output every time, not creative variation, and every call
        # (single-pass/map/reduce alike) shares the same max_tokens ceiling
        # for the reason noted at the REDUCE step above.
        return await self._llm.summarize(
            model_id=self._model_id,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=self._summary_max_tokens,
            temperature=0.0,
            check_limits=check_limits,
        )
