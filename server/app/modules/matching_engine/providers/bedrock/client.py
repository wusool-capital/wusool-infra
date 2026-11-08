"""Real AWS Bedrock implementation of `BedrockClient`, built on Pydantic AI
agents over the Converse API.

Each agent's `output_type` is a `ToolOutput` with no text output allowed,
so Bedrock is forced to call the output tool (`toolChoice: any`), and the
agent validates the result into its schema (`schemas.py`) before we see it.
A failed schema check, or an extracted monetary requirement not written as
`USD <amount>`, gets one retry with the error sent back to the model; a
second failure raises `BedrockInvocationError` (fail closed).

Transient-error retries, metadata-only logging and content-free errors
come from the shared `utilities.providers.bedrock.agent.run_bedrock_agent`.
The boto3 client keeps its own timeouts (see `boto_client.py`).
"""

from __future__ import annotations

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.bedrock import BedrockModelSettings

from app.modules.matching_engine.application.ports.llm_types import (
    ExtractedRequirements,
    InferenceConfig,
)
from app.modules.matching_engine.domain.matching.entities import ReasoningOutcome
from app.modules.matching_engine.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.matching_engine.providers.bedrock.schemas import (
    ExtractedRequirementProfile,
    ReasoningResult,
)
from app.modules.utilities.providers.bedrock.agent import (
    bedrock_model,
    run_bedrock_agent,
    structured_agent,
)

_EXTRACTION_OPERATION = "extraction"
_REASONING_OPERATION = "reasoning"
# One repair round, matching the old validate-repair-retry-then-fail-closed policy.
_OUTPUT_RETRIES = 1


def _check_monetary(output: ExtractedRequirementProfile) -> ExtractedRequirementProfile:
    issue = output.monetary_issue()
    if issue:
        raise ModelRetry(issue)
    return output


def _settings(config: InferenceConfig) -> BedrockModelSettings:
    # `top_p` stays configured but unused: Anthropic models reject it alongside temperature.
    return BedrockModelSettings(max_tokens=config.max_tokens, temperature=config.temperature)


class BedrockConverseClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()
        # No `instructions`: this module's prompts are entirely user-turn.
        self.extraction_agent: Agent[None, ExtractedRequirementProfile] = structured_agent(
            ExtractedRequirementProfile,
            name="requirement_profile",
            output_retries=_OUTPUT_RETRIES,
        )
        self.extraction_agent.output_validator(_check_monetary)
        self.reasoning_agent: Agent[None, ReasoningResult] = structured_agent(
            ReasoningResult, name="match_reasoning", output_retries=_OUTPUT_RETRIES
        )

    async def extract_requirements(
        self,
        *,
        model_id: str,
        prompt: str,
        inference_config: InferenceConfig,
    ) -> ExtractedRequirements:
        model = bedrock_model(model_id, self._client)
        settings = _settings(inference_config)
        output = await run_bedrock_agent(
            lambda: self.extraction_agent.run(prompt, model=model, model_settings=settings),
            model_id=model_id,
            operation=_EXTRACTION_OPERATION,
        )
        return output.to_domain()

    async def generate_reasoning(
        self,
        *,
        model_id: str,
        prompt: str,
        inference_config: InferenceConfig,
    ) -> ReasoningOutcome:
        model = bedrock_model(model_id, self._client)
        settings = _settings(inference_config)
        output = await run_bedrock_agent(
            lambda: self.reasoning_agent.run(prompt, model=model, model_settings=settings),
            model_id=model_id,
            operation=_REASONING_OPERATION,
        )
        return output.to_domain()
