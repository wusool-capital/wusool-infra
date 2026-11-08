"""`BedrockConverseClient` on Pydantic AI, driven by `FunctionModel` — no AWS."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import boto3
import pytest
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import RetryPromptPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.modules.enrichment.domain.proposals import ExtractedField
from app.modules.enrichment.providers.bedrock import client as client_module
from app.modules.enrichment.providers.bedrock.client import BedrockConverseClient
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.providers.bedrock import agent as agent_module

_SECRET = "Acme's revenue is AED 42m"

_FIELD: JsonObject = {
    "field_name": "est_revenue",
    "value": "5000000",
    "source_url": "https://example.com",
    "confidence": "high",
    "rationale": "press release",
}

type Responder = Callable[[int], JsonObject]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> BedrockConverseClient:
    monkeypatch.setattr(
        client_module,
        "get_bedrock_runtime_client",
        lambda: boto3.client("bedrock-runtime", region_name="eu-central-1"),
    )
    monkeypatch.setattr(agent_module, "_BASE_DELAY_SECONDS", 0.0)
    return BedrockConverseClient()


class _Model:
    """Answers each request through the output tool; records retry prompts."""

    def __init__(self, respond: Responder) -> None:
        self.respond = respond
        self.calls = 0
        self.retry_prompts: list[str] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.retry_prompts.extend(
            str(part.content)
            for part in messages[-1].parts
            if isinstance(part, ToolReturnPart | RetryPromptPart)
        )
        self.calls += 1
        args = self.respond(self.calls)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


def _extract(client: BedrockConverseClient, model: _Model) -> tuple[ExtractedField, ...]:
    with client.agent.override(model=FunctionModel(model)):
        return asyncio.run(
            client.extract_fields(model_id="m", prompt="p", temperature=0.0, max_tokens=100)
        )


def test_returns_typed_domain_fields(client: BedrockConverseClient) -> None:
    model = _Model(lambda _: {"fields": [_FIELD]})
    assert _extract(client, model) == (
        ExtractedField(
            field_name="est_revenue",
            value="5000000",
            source_url="https://example.com",
            confidence="high",
            rationale="press release",
        ),
    )
    assert model.calls == 1


def test_retries_a_schema_failure_once(client: BedrockConverseClient) -> None:
    bad = {**_FIELD, "confidence": "certain"}
    model = _Model(lambda call: {"fields": [bad if call == 1 else _FIELD]})
    fields = _extract(client, model)
    assert fields[0].confidence == "high"
    assert model.calls == 2
    assert "confidence" in model.retry_prompts[0]


def test_schema_failure_twice_raises_without_model_output(client: BedrockConverseClient) -> None:
    model = _Model(lambda _: {"fields": [{"field_name": _SECRET}]})
    with pytest.raises(BedrockInvocationError) as raised:
        _extract(client, model)
    assert _SECRET not in str(raised.value)
    assert raised.value.__cause__ is None
    assert model.calls == 2


def test_retries_a_throttled_call(client: BedrockConverseClient) -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise ModelHTTPError(
                429, "m", provider_error_code="ThrottlingException", body={"message": _SECRET}
            )
        return {"fields": [_FIELD]}

    model = _Model(respond)
    assert len(_extract(client, model)) == 1
    assert model.calls == 2
