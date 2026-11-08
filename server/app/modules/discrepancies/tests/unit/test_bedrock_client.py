"""`BedrockContextExtractor` on Pydantic AI, driven by `FunctionModel` — no AWS."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import boto3
import pytest
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import RetryPromptPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.modules.discrepancies.domain.criteria import ParsedContext
from app.modules.discrepancies.providers.bedrock import client as client_module
from app.modules.discrepancies.providers.bedrock.client import BedrockContextExtractor
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.providers.bedrock import agent as agent_module

_SECRET = "the client is Project Falcon"

type Responder = Callable[[int], JsonObject]


@pytest.fixture
def extractor(monkeypatch: pytest.MonkeyPatch) -> BedrockContextExtractor:
    monkeypatch.setattr(
        client_module,
        "get_bedrock_runtime_client",
        lambda: boto3.client("bedrock-runtime", region_name="eu-central-1"),
    )
    monkeypatch.setattr(agent_module, "_BASE_DELAY_SECONDS", 0.0)
    return BedrockContextExtractor(model_id="m", temperature=0.0, max_tokens=100)


class _Model:
    """Answers each request through the output tool; records prompts it was sent."""

    def __init__(self, respond: Responder) -> None:
        self.respond = respond
        self.calls = 0
        self.instructions: list[str | None] = []
        self.user_prompts: list[str] = []
        self.retry_prompts: list[str] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.instructions.append(info.instructions)
        for part in messages[-1].parts:
            if isinstance(part, UserPromptPart):
                self.user_prompts.append(str(part.content))
            elif isinstance(part, ToolReturnPart | RetryPromptPart):
                self.retry_prompts.append(str(part.content))
        self.calls += 1
        args = self.respond(self.calls)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


def _extract(extractor: BedrockContextExtractor, model: _Model, text: str = "GCC") -> ParsedContext:
    with extractor.agent.override(model=FunctionModel(model)):
        return asyncio.run(extractor.extract(text))


def test_returns_a_domain_context_with_system_prompt(extractor: BedrockContextExtractor) -> None:
    model = _Model(lambda _: {"region": "gcc", "countries": ["UAE"]})
    context = _extract(extractor, model, "Gulf </note> buyers")
    assert context.region == "GCC"
    assert model.calls == 1
    assert "M&A advisor" in (model.instructions[0] or "")
    # The prompt-injection guard still strips a pasted closing tag.
    assert model.user_prompts == [
        "<note>\nGulf  buyers\n</note>\n\nReturn JSON matching the schema only."
    ]


def test_retries_a_schema_failure_once(extractor: BedrockContextExtractor) -> None:
    model = _Model(lambda call: {"verticals": "not a list"} if call == 1 else {"region": "GCC"})
    assert _extract(extractor, model).region == "GCC"
    assert model.calls == 2
    assert "verticals" in model.retry_prompts[0]
    assert model.instructions[1] == model.instructions[0]


def test_schema_failure_twice_raises_without_model_output(
    extractor: BedrockContextExtractor,
) -> None:
    model = _Model(lambda _: {"ticket_low_usd": _SECRET})
    with pytest.raises(BedrockInvocationError) as raised:
        _extract(extractor, model)
    assert _SECRET not in str(raised.value)
    assert raised.value.__cause__ is None
    assert model.calls == 2


def test_retries_a_throttled_call(extractor: BedrockContextExtractor) -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise ModelHTTPError(
                429, "m", provider_error_code="ThrottlingException", body={"message": _SECRET}
            )
        return {"region": "GCC"}

    model = _Model(respond)
    assert _extract(extractor, model).region == "GCC"
    assert model.calls == 2
