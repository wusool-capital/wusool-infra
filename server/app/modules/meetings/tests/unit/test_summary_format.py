"""Scannable summary format: length budget, prompt contents and render order."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.modules.meetings.application.summarize import SummarizationService
from app.modules.meetings.domain.prompts import (
    SummaryBudget,
    build_merge_prompt,
    build_single_pass_summary_prompt,
    summary_budget,
)
from app.modules.meetings.domain.rendering import render_summary_text
from app.modules.meetings.domain.roles import MeetingRole
from app.modules.meetings.domain.summary import MeetingSummary, SummaryNote

_SHORT = SummaryBudget(min_topics=1, max_topics=2, max_words=120)
_MEDIUM = SummaryBudget(min_topics=3, max_topics=4, max_words=350)
_LONG = SummaryBudget(min_topics=6, max_topics=8, max_words=700)
_SELLER = {MeetingRole.SELLER: "Al Waha Foods"}


@pytest.mark.parametrize(
    ("words", "expected"),
    [(20, _SHORT), (2000, _SHORT), (2001, _MEDIUM), (8000, _MEDIUM), (8001, _LONG), (40000, _LONG)],
)
def test_budget_grows_with_transcript_length(words: int, expected: SummaryBudget) -> None:
    assert summary_budget(words) == expected


@pytest.mark.parametrize("companies", [None, _SELLER])
def test_prompt_carries_budget_gist_and_style(companies: dict[MeetingRole, str] | None) -> None:
    prompt = build_single_pass_summary_prompt("hello", budget=_MEDIUM, companies=companies)
    assert "3-4 objects" in prompt
    assert "about 350 words at most" in prompt
    assert "60 words at most" in prompt
    assert "British spelling" in prompt
    assert "Only notes shrink" in prompt
    assert "1500 words" not in prompt


def test_momentum_only_for_deal_meetings() -> None:
    internal = build_single_pass_summary_prompt("hello", budget=_SHORT, companies=None)
    seller = build_single_pass_summary_prompt("hello", budget=_SHORT, companies=_SELLER)
    assert '"deal_momentum":' not in internal
    assert '"deal_momentum":' in seller


def test_few_shot_outputs_are_valid_json() -> None:
    prompt = build_single_pass_summary_prompt("hello", budget=_SHORT, companies=_SELLER)
    outputs = prompt.split("@@@EXAMPLE_OUTPUT_START@@@\n")[1:]
    assert len(outputs) == 2
    for output in outputs:
        parsed = json.loads(output.split("\n@@@EXAMPLE_OUTPUT_END@@@")[0])
        assert len(parsed["executive_summary"].split()) <= 60


def test_speaker_rule_trusts_assigned_names_only() -> None:
    prompt = build_single_pass_summary_prompt("hello", budget=_SHORT)
    assert "assigned by a user" in prompt
    assert "'Speaker 2'" in prompt
    assert "'Participant'" in prompt


def test_merge_prompt_writes_gist_fresh() -> None:
    prompt = build_merge_prompt(["{}", "{}"], budget=_LONG)
    assert "Write executive_summary fresh" in prompt
    assert "6-8 objects" in prompt


def test_render_order_puts_notes_last() -> None:
    summary = MeetingSummary(
        title="t",
        executive_summary="Floor agreed at AED 42m.",
        notes=[
            SummaryNote(topic="Valuation", points=["7x adjusted EBITDA."]),
            SummaryNote(topic="Empty"),
        ],
        decisions=["Floor of AED 42m."],
        action_items=["Sinan: send the request, by 12 Nov 2026."],
        claims_to_verify=["AED 1.1m add-back: no payroll record."],
        risks=["Carrefour is 35% of revenue."],
        deal_momentum="Advanced — floor agreed.",
        keywords=["floor price", "EBITDA"],
    )
    assert render_summary_text(summary).split("\n\n") == [
        "Floor agreed at AED 42m.",
        "Next steps:\n- Sinan: send the request, by 12 Nov 2026.",
        "Decisions:\n- Floor of AED 42m.",
        "Deal momentum: Advanced — floor agreed.",
        "To verify:\n- AED 1.1m add-back: no payroll record.",
        "Risks:\n- Carrefour is 35% of revenue.",
        "Keywords: floor price, EBITDA",
        "Notes",
        "Valuation:\n- 7x adjusted EBITDA.",
    ]


def test_render_skips_empty_sections() -> None:
    assert (
        render_summary_text(MeetingSummary(title="t", executive_summary="Only a gist."))
        == "Only a gist."
    )


class _RecordingLLM:
    def __init__(self, deal_momentum: str = "") -> None:
        self.prompts: list[str] = []
        self.deal_momentum = deal_momentum

    async def summarize(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        check_limits: bool,
    ) -> MeetingSummary:
        self.prompts.append(prompt)
        return MeetingSummary(title="t", executive_summary="g", deal_momentum=self.deal_momentum)


def test_service_sizes_budget_from_whole_transcript() -> None:
    llm = _RecordingLLM()
    service = SummarizationService(
        llm, model_id="m", summary_max_tokens=100, summary_max_tokens_per_chunk=8000
    )
    transcript = " ".join(["word"] * 3000)

    asyncio.run(service.summarize(transcript, companies=None, meeting_date=None))

    assert len(llm.prompts) == 1
    assert "3-4 objects" in llm.prompts[0]


@pytest.mark.parametrize(
    ("companies", "expected"),
    [(None, ""), ({MeetingRole.INTERNAL: "Wusool"}, ""), (_SELLER, "N/A — internal update")],
)
def test_momentum_is_dropped_without_a_counterparty(
    companies: dict[MeetingRole, str] | None, expected: str
) -> None:
    llm = _RecordingLLM(deal_momentum="N/A — internal update")
    service = SummarizationService(
        llm, model_id="m", summary_max_tokens=100, summary_max_tokens_per_chunk=8000
    )
    transcript = " ".join(["word"] * 50)

    summary = asyncio.run(service.summarize(transcript, companies=companies, meeting_date=None))

    assert summary.deal_momentum == expected
