"""Scores proofread against labelled excerpts, on real Bedrock.

    AWS_PROFILE=wusool-sso uv run python -m app.modules.meetings.evals.eval_proofread \
        eu.anthropic.claude-sonnet-4-6 eu.anthropic.claude-haiku-4-5-20251001-v1:0

A fix line counts as caught when a suggestion contains every expected term
(ignoring case).
A suggestion on a `keep` line, or one missing the terms, is a false fix.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from botocore.config import Config
from pydantic import BaseModel, Field

from app.modules.meetings.application.corrections import CorrectionService
from app.modules.meetings.domain.corrections import CorrectionContext, TranscriptSegment
from app.modules.meetings.providers.bedrock import client as client_module
from app.modules.meetings.providers.bedrock.client import BedrockConverseClient
from app.modules.utilities.providers.bedrock.client_factory import build_bedrock_runtime_client

_CASES = Path(__file__).with_name("proofread_cases.json")


class _Line(BaseModel):
    id: str
    speaker: str
    text: str
    fix: list[str] = Field(default_factory=list)
    keep: bool = False


class _Context(BaseModel):
    title: str
    names: list[str]
    vocabulary: list[str]


class _Case(BaseModel):
    name: str
    context: _Context
    lines: list[_Line]


class _Cases(BaseModel):
    cases: list[_Case]


@dataclass
class _Score:
    expected: int = 0
    caught: int = 0
    false_fixes: int = 0
    suggestions: int = 0
    seconds: float = 0.0


async def _score_model(model_id: str, cases: list[_Case]) -> _Score:
    service = CorrectionService(
        BedrockConverseClient(),
        model_id=model_id,
        max_tokens=4096,
        max_chars_per_batch=12_000,
        gate=asyncio.Semaphore(4),
    )
    score = _Score()
    for case in cases:
        started = time.monotonic()
        result = await service.suggest(
            [TranscriptSegment(line.id, line.text, speaker=line.speaker) for line in case.lines],
            CorrectionContext(
                title=case.context.title,
                names=tuple(case.context.names),
                vocabulary=tuple(case.context.vocabulary),
            ),
        )
        score.seconds += time.monotonic() - started
        by_id = {s.segment_id: s.suggested for s in result.suggestions}
        score.suggestions += len(by_id)
        for line in case.lines:
            suggested = by_id.get(line.id)
            if line.fix:
                score.expected += 1
                if suggested and all(term.lower() in suggested.lower() for term in line.fix):
                    score.caught += 1
                elif suggested:
                    score.false_fixes += 1
                    print(f"  wrong fix [{case.name}] {line.text!r} -> {suggested!r}")
                else:
                    print(f"  missed [{case.name}] {line.text!r}")
            elif suggested:
                score.false_fixes += 1
                print(f"  false fix [{case.name}] {line.text!r} -> {suggested!r}")
    return score


async def main(model_ids: list[str]) -> None:
    # The module's own factory reads server settings; an eval only needs AWS credentials.
    boto = build_bedrock_runtime_client(
        region_name="eu-central-1", config=Config(connect_timeout=10, read_timeout=120)
    )
    setattr(client_module, "get_bedrock_runtime_client", lambda: boto)  # noqa: B010
    cases = _Cases.model_validate(json.loads(_CASES.read_text())).cases
    for model_id in model_ids:
        print(model_id)
        score = await _score_model(model_id, cases)
        precision = (score.caught / score.suggestions) if score.suggestions else 1.0
        print(
            f"  caught {score.caught}/{score.expected} "
            f"({score.caught / score.expected:.0%}), false fixes {score.false_fixes}, "
            f"precision {precision:.0%}, {score.seconds:.0f}s total\n"
        )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["eu.anthropic.claude-sonnet-4-6"]))
