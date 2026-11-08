"""Real AWS Bedrock implementation of `SummarizerLLM` and `CorrectorLLM`,
built on Pydantic AI agents over the Converse API.

Each agent's `output_type` is a `ToolOutput` with no text output allowed,
so Bedrock is forced to call the output tool (`toolChoice: any`), and the
agent validates the result into the schema before we see it. A failed
schema check or a broken summary length rule (`summary_limit_issues`) gets
one retry with the error sent back to the model; after that a schema
failure raises and a length overshoot is accepted, since a slightly long
summary beats a failed meeting.

Transient-error retries, metadata-only logging and content-free errors
come from the shared `utilities.providers.bedrock.agent.run_bedrock_agent`.
The boto3 client keeps its 300s `read_timeout` (see `boto_client.py`).
"""

from __future__ import annotations

from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
from pydantic_ai.models.bedrock import BedrockModelSettings

from app.modules.meetings.domain.corrections import CorrectionSuggestion
from app.modules.meetings.domain.summary import MeetingSummary, summary_limit_issues
from app.modules.meetings.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.meetings.providers.bedrock.schemas import (
    MeetingSummarySchema,
    TranscriptCorrectionsSchema,
)
from app.modules.utilities.providers.bedrock.agent import bedrock_model, run_bedrock_agent

_OPERATION = "summarization"
_CORRECTION_OPERATION = "transcript_correction"
# One repair round, matching the old validate-repair-retry policy.
_OUTPUT_RETRIES = 1


def _check_limits(ctx: RunContext[bool], output: MeetingSummarySchema) -> MeetingSummarySchema:
    if not ctx.deps or ctx.retry >= ctx.max_retries:
        return output
    issues = summary_limit_issues(output.to_domain())
    if issues:
        raise ModelRetry(" ".join(issues))
    return output


class BedrockConverseClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()
        # deps is check_limits: map-step excerpts are dense on purpose, so only final
        # summaries are held to the length rules.
        self.summary_agent: Agent[bool, MeetingSummarySchema] = Agent(
            name="meeting_summary",
            deps_type=bool,
            output_type=ToolOutput(MeetingSummarySchema, name="meeting_summary"),
            retries={"output": _OUTPUT_RETRIES},
        )
        self.summary_agent.output_validator(_check_limits)
        self.corrections_agent: Agent[None, TranscriptCorrectionsSchema] = Agent(
            name="transcript_corrections",
            output_type=ToolOutput(TranscriptCorrectionsSchema, name="transcript_corrections"),
            retries={"output": _OUTPUT_RETRIES},
        )

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
        model = bedrock_model(model_id, self._client)
        settings = BedrockModelSettings(max_tokens=max_tokens, temperature=temperature)
        output = await run_bedrock_agent(
            lambda: self.summary_agent.run(
                prompt,
                model=model,
                instructions=system_prompt,
                model_settings=settings,
                deps=check_limits,
            ),
            model_id=model_id,
            operation=_OPERATION,
        )
        return output.to_domain()

    async def suggest_corrections(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> list[CorrectionSuggestion]:
        model = bedrock_model(model_id, self._client)
        settings = BedrockModelSettings(max_tokens=max_tokens, temperature=temperature)
        output = await run_bedrock_agent(
            lambda: self.corrections_agent.run(
                prompt, model=model, instructions=system_prompt, model_settings=settings
            ),
            model_id=model_id,
            operation=_CORRECTION_OPERATION,
        )
        return output.to_domain()
