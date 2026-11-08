"""Real AWS Bedrock implementation of `ExtractionClient`, built on a
Pydantic AI agent over the Converse API.

The agent's `output_type` is a `ToolOutput` with no text output allowed, so
Bedrock is forced to call the output tool, and the agent validates the
result into `ExtractedFields`. A schema failure gets one retry with the
error sent back to the model in the same conversation; a second failure
raises `BedrockInvocationError`.

Transient-error retries, metadata-only logging and content-free errors
come from the shared `utilities.providers.bedrock.agent.run_bedrock_agent`.
"""

from __future__ import annotations

from pydantic_ai import Agent, ToolOutput
from pydantic_ai.models.bedrock import BedrockModelSettings

from app.modules.enrichment.domain.proposals import ExtractedField
from app.modules.enrichment.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.enrichment.providers.bedrock.schemas import ExtractedFields
from app.modules.utilities.providers.bedrock.agent import bedrock_model, run_bedrock_agent

_OPERATION = "enrichment_extraction"
# One repair round, matching the old validate-repair-retry policy.
_OUTPUT_RETRIES = 1


class BedrockConverseClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()
        self.agent: Agent[None, ExtractedFields] = Agent(
            name="enrichment_extraction",
            output_type=ToolOutput(ExtractedFields, name="extracted_fields"),
            retries={"output": _OUTPUT_RETRIES},
        )

    async def extract_fields(
        self,
        *,
        model_id: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[ExtractedField, ...]:
        model = bedrock_model(model_id, self._client)
        settings = BedrockModelSettings(max_tokens=max_tokens, temperature=temperature)
        output = await run_bedrock_agent(
            lambda: self.agent.run(prompt, model=model, model_settings=settings),
            model_id=model_id,
            operation=_OPERATION,
        )
        return output.to_domain()
