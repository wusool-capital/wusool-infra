"""A fake implementing `BedrockClient` for unit/e2e tests — no AWS calls."""

from app.modules.llm.domain.bedrock_client import InferenceConfig


class FakeBedrockClient:
    """Returns a scripted sequence of responses per operation, one per call.
    Set `structured_responses`/`reasoning_responses` to a list; each call
    pops the next one. A response of `"__raise__"` raises instead (for
    testing permanent-failure paths in the calling service).
    """

    def __init__(
        self,
        structured_responses: list[dict] | None = None,
        reasoning_responses: list[dict] | None = None,
    ) -> None:
        self.structured_responses = list(structured_responses or [])
        self.reasoning_responses = list(reasoning_responses or [])
        self.structured_calls: list[str] = []
        self.reasoning_calls: list[str] = []

    async def generate_structured(
        self, *, model_id: str, prompt: str, inference_config: InferenceConfig, output_schema: dict
    ) -> dict:
        self.structured_calls.append(prompt)
        if not self.structured_responses:
            raise AssertionError(
                "FakeBedrockClient.generate_structured called with no responses left"
            )
        response = self.structured_responses.pop(0)
        if response == "__raise__":
            raise RuntimeError("simulated permanent Bedrock failure")
        return response

    async def generate_reasoning(
        self, *, model_id: str, prompt: str, inference_config: InferenceConfig, output_schema: dict
    ) -> dict:
        self.reasoning_calls.append(prompt)
        if not self.reasoning_responses:
            raise AssertionError(
                "FakeBedrockClient.generate_reasoning called with no responses left"
            )
        response = self.reasoning_responses.pop(0)
        if response == "__raise__":
            raise RuntimeError("simulated permanent Bedrock failure")
        return response
