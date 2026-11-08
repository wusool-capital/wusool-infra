"""`LeadBedrockClient` on Pydantic AI, driven by `FunctionModel` — no AWS."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

import boto3
import pytest
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.providers.bedrock import client as client_module
from app.modules.lead_magnets.providers.bedrock.client import LeadBedrockClient
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.providers.bedrock import agent as agent_module

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

_SECRET = "Acme's EBITDA is AED 9m"

type Responder = Callable[[int], JsonObject]


class _Model:
    """Answers each request through the output tool; records model ids and settings."""

    def __init__(self, respond: Responder) -> None:
        self.respond = respond
        self.calls = 0
        self.model_ids: list[str] = []
        self.max_tokens: list[int | None] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.calls += 1
        settings = info.model_settings or {}
        self.max_tokens.append(settings.get("max_tokens"))
        args = self.respond(self.calls)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


@pytest.fixture
def model() -> _Model:
    return _Model(lambda _: {"queries": ["fit-out contractors UAE"]})


def _client(monkeypatch: pytest.MonkeyPatch, model: _Model) -> LeadBedrockClient:
    monkeypatch.setattr(
        client_module,
        "get_bedrock_runtime_client",
        lambda: boto3.client("bedrock-runtime", region_name="eu-central-1"),
    )

    def fake_bedrock_model(model_id: str, _client: BedrockRuntimeClient) -> FunctionModel:
        model.model_ids.append(model_id)
        return FunctionModel(model)

    monkeypatch.setattr(client_module, "bedrock_model", fake_bedrock_model)
    monkeypatch.setattr(agent_module, "_BASE_DELAY_SECONDS", 0.0)
    return LeadBedrockClient()


def test_plan_search_queries_returns_typed_output_on_haiku(
    monkeypatch: pytest.MonkeyPatch, model: _Model
) -> None:
    client = _client(monkeypatch, model)
    result = asyncio.run(client.plan_search_queries(prompt="p"))
    assert result.queries == ["fit-out contractors UAE"]
    assert model.model_ids == [get_settings().lead_magnet_model_haiku]
    assert model.max_tokens == [512]


def test_qualify_buyer_returns_typed_note_on_haiku(monkeypatch: pytest.MonkeyPatch) -> None:
    model = _Model(lambda _: {"priority": "high", "note": "Strong fit."})
    client = _client(monkeypatch, model)
    result = asyncio.run(client.qualify_buyer(prompt="p"))
    assert (result.priority, result.note) == ("high", "Strong fit.")
    assert model.max_tokens == [2048]


def test_sonnet_operation_uses_sonnet_and_its_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    model = _Model(lambda _: {})
    client = _client(monkeypatch, model)
    # An empty object fails EnrichResult; only the request shape matters here.
    with pytest.raises(BedrockInvocationError):
        asyncio.run(client.enrich(prompt="p"))
    assert model.model_ids == [get_settings().lead_magnet_model_sonnet]
    assert model.max_tokens == [1024]


def test_schema_failure_raises_immediately_without_model_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _Model(lambda _: {"queries": _SECRET})
    client = _client(monkeypatch, model)
    with pytest.raises(BedrockInvocationError) as raised:
        asyncio.run(client.plan_search_queries(prompt="p"))
    assert model.calls == 1
    assert _SECRET not in str(raised.value)
    assert raised.value.__cause__ is None


def test_retries_a_throttled_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise ModelHTTPError(
                429, "m", provider_error_code="ThrottlingException", body={"message": _SECRET}
            )
        return {"priority": "now", "note": "n"}

    model = _Model(respond)
    client = _client(monkeypatch, model)
    assert asyncio.run(client.advise_readiness(prompt="p")).priority == "now"
    assert model.calls == 2
