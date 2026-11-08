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

from app.modules.meetings.providers.bedrock import client as client_module
from app.modules.meetings.providers.bedrock.client import BedrockConverseClient
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.providers.bedrock import agent as agent_module

_SECRET = "Khalid's floor is AED 42m"


def _summary(gist: str = "Floor agreed at AED 42m.") -> JsonObject:
    return {
        "title": "t",
        "executive_summary": gist,
        "notes": [{"topic": "Valuation", "points": ["7x adjusted EBITDA."]}],
        "decisions": ["Floor of AED 42m."],
        "action_items": [],
        "claims_to_verify": [],
        "risks": [],
        "deal_momentum": "",
        "keywords": ["floor price"],
    }


_LONG_GIST = " ".join(["word"] * 80)

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
        # The retry for an output tool comes back as that tool's return.
        self.retry_prompts.extend(
            str(part.content)
            for part in messages[-1].parts
            if isinstance(part, ToolReturnPart | RetryPromptPart)
        )
        self.calls += 1
        args = self.respond(self.calls)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


def _summarize(client: BedrockConverseClient, model: _Model, *, check_limits: bool = True):  # noqa: ANN202
    with client.summary_agent.override(model=FunctionModel(model)):
        return asyncio.run(
            client.summarize(
                model_id="eu.anthropic.claude-sonnet-4-6",
                prompt="p",
                system_prompt="s",
                max_tokens=100,
                temperature=0.0,
                check_limits=check_limits,
            )
        )


def test_returns_a_typed_domain_summary(client: BedrockConverseClient) -> None:
    model = _Model(lambda _: _summary())
    summary = _summarize(client, model)
    assert summary.executive_summary == "Floor agreed at AED 42m."
    assert summary.notes[0].points == ["7x adjusted EBITDA."]
    assert model.calls == 1


def test_retries_a_long_gist_once(client: BedrockConverseClient) -> None:
    model = _Model(lambda call: _summary(_LONG_GIST if call == 1 else "Short gist."))
    summary = _summarize(client, model)
    assert summary.executive_summary == "Short gist."
    assert model.calls == 2
    assert "80 words" in model.retry_prompts[0]


def test_accepts_a_long_gist_after_the_retry(client: BedrockConverseClient) -> None:
    model = _Model(lambda _: _summary(_LONG_GIST))
    summary = _summarize(client, model)
    assert summary.executive_summary == _LONG_GIST
    assert model.calls == 2


def test_excerpts_skip_the_length_rules(client: BedrockConverseClient) -> None:
    model = _Model(lambda _: _summary(_LONG_GIST))
    _summarize(client, model, check_limits=False)
    assert model.calls == 1


def test_schema_failure_raises_without_model_output(client: BedrockConverseClient) -> None:
    model = _Model(lambda _: {"executive_summary": _SECRET})
    with pytest.raises(BedrockInvocationError) as raised:
        _summarize(client, model)
    assert _SECRET not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__


def test_retries_a_throttled_call(client: BedrockConverseClient) -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise ModelHTTPError(
                429, "m", provider_error_code="ThrottlingException", body={"message": _SECRET}
            )
        return _summary()

    model = _Model(respond)
    assert _summarize(client, model).title == "t"
    assert model.calls == 2


def test_non_transient_error_is_not_retried(client: BedrockConverseClient) -> None:
    def respond(_: int) -> JsonObject:
        raise ModelHTTPError(
            400, "m", provider_error_code="ValidationException", body={"message": _SECRET}
        )

    model = _Model(respond)
    with pytest.raises(BedrockInvocationError, match="ValidationException") as raised:
        _summarize(client, model)
    assert _SECRET not in str(raised.value)
    assert model.calls == 1


def test_corrections_return_domain_suggestions(client: BedrockConverseClient) -> None:
    suggestion = {"segment_id": "s1", "original": "a", "suggested": "b", "reason": "typo"}
    model = _Model(lambda _: {"suggestions": [suggestion]})
    with client.corrections_agent.override(model=FunctionModel(model)):
        result = asyncio.run(
            client.suggest_corrections(
                model_id="m", prompt="p", system_prompt="s", max_tokens=100, temperature=0.0
            )
        )
    assert [(s.segment_id, s.suggested) for s in result] == [("s1", "b")]
