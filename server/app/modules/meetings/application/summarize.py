"""Standalone collaborator, not a `ServiceBase` mixin — nothing outside
`PublishMixin` calls this directly, exactly how `matching_engine`'s
`MatchReasoningService` sits outside its own mixin facade (see
`application/base.py`'s docstring there).

Ported from Scribe's `app.ai.summarizer.HierarchicalSummarizer`, converting
its output into this module's own `MeetingSummary`/`SummaryNote` domain
dataclasses instead of Scribe's `app.ai.domain.MeetingSummary`.
`providers/bedrock/schemas.py` deliberately stops at a validated dict — the
dict -> domain-dataclass conversion is this module's job instead, so it
happens once, in the one place that already needs the domain type.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

from app.modules.meetings.application.ports.summarizer_llm import SummarizerLLM
from app.modules.meetings.domain.chunking import chunk_text
from app.modules.meetings.domain.prompts import (
    SYSTEM_PROMPT,
    build_chunk_summary_prompt,
    build_merge_prompt,
    build_single_pass_summary_prompt,
)
from app.modules.meetings.domain.roles import MeetingRole
from app.modules.meetings.domain.summary import MeetingSummary, SummaryNote
from app.modules.utilities.domain.json_types import JsonObject

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
    title="No meeting content to summarize",
    executive_summary=(
        "This meeting's recording didn't capture enough spoken content to "
        "produce a summary — the transcript was empty or too short."
    ),
)

_STRING_LIST_KEYS = ("decisions", "action_items", "claims_to_verify", "risks", "keywords")


def _to_notes(value: Any) -> list[SummaryNote]:
    if not isinstance(value, list):
        return []
    notes: list[SummaryNote] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", ""))
        points = item.get("points", [])
        note_points = list(points) if isinstance(points, list) else []
        notes.append(SummaryNote(topic=topic, points=note_points))
    return notes


def _to_meeting_summary(data: JsonObject) -> MeetingSummary:
    """Convert the validated dict `SummarizerLLM.summarize` returns into
    this module's `MeetingSummary`. `BedrockConverseClient.summarize`
    already validates the shape against `MeetingSummarySchema` before
    returning, so this doesn't need to redo Scribe's degrade-don't-raise
    dict-coercion dance — but it still reads with `.get(key, default)`
    rather than bare indexing, defensively, in case a future provider swap
    is less strict than Bedrock's forced-tool-call schema.
    """
    return MeetingSummary(
        title=str(data.get("title", "")),
        executive_summary=str(data.get("executive_summary", "")),
        notes=_to_notes(data.get("notes")),
        deal_momentum=str(data.get("deal_momentum", "")),
        **{key: list(data.get(key, [])) for key in _STRING_LIST_KEYS},
    )


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
        if len(transcript_text.split()) < _MIN_TRANSCRIPT_WORDS:
            return _NO_CONTENT_SUMMARY

        chunks = chunk_text(
            transcript_text, max_tokens_per_chunk=self._summary_max_tokens_per_chunk
        )

        if len(chunks) <= 1:
            single = chunks[0] if chunks else ""
            raw = await self._call_llm(
                build_single_pass_summary_prompt(
                    single, companies=companies, meeting_date=meeting_date
                )
            )
            return _to_meeting_summary(raw)

        # MAP: one summarize() call per chunk. Run concurrently — unlike
        # Scribe, which does this serially — since nothing here forbids
        # it and Scribe's own comments flag it as an easy win; the REDUCE
        # step below still waits on all of them anyway.
        chunk_summaries = await asyncio.gather(
            *(
                self._call_llm(
                    build_chunk_summary_prompt(
                        chunk, companies=companies, meeting_date=meeting_date
                    )
                )
                for chunk in chunks
            )
        )

        # REDUCE: same output-token budget as every other call here (see
        # _call_llm) — the map step's prompt asks it to favor completeness
        # over brevity and preserve every figure verbatim, which a smaller
        # budget would quietly work against.
        merge_raw = await self._call_llm(
            build_merge_prompt(
                [json.dumps(summary) for summary in chunk_summaries],
                companies=companies,
                meeting_date=meeting_date,
            )
        )
        return _to_meeting_summary(merge_raw)

    async def _call_llm(self, prompt: str) -> JsonObject:
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
        )
