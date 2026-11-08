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

from app.modules.matching_engine.application.ports.llm_types import (
    ExtractedRequirements,
    InferenceConfig,
)
from app.modules.matching_engine.domain.matching.entities import ReasoningOutcome
from app.modules.matching_engine.domain.requirements import AdvisorLimits
from app.modules.matching_engine.providers.bedrock import client as client_module
from app.modules.matching_engine.providers.bedrock.client import BedrockConverseClient
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.providers.bedrock import agent as agent_module

_SECRET = "Acme's walk-away is USD 42M"
_CONFIG = InferenceConfig(temperature=0.2, max_tokens=100, top_p=0.9)


def _extraction(revenue: str = "USD 50M") -> JsonObject:
    return {
        "hard_requirements": [
            {
                "criterion": "minimum_revenue",
                "value": revenue,
                "source": "llm_extracted",
                "confidence": "low",
                "human_confirmed": False,
            }
        ],
        "soft_preferences": [],
        "strategic_thesis": "Roll-up of regional fintechs",
        "scoring_rubric": {"minimum_revenue": 1.0},
        "data_confidence": 0.6,
        "advisor_limits": {"ticket_max": "USD 15M"},
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
        # The retry for an output tool comes back as that tool's return.
        self.retry_prompts.extend(
            str(part.content)
            for part in messages[-1].parts
            if isinstance(part, ToolReturnPart | RetryPromptPart)
        )
        self.calls += 1
        args = self.respond(self.calls)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


def _extract(client: BedrockConverseClient, model: _Model) -> ExtractedRequirements:
    with client.extraction_agent.override(model=FunctionModel(model)):
        return asyncio.run(
            client.extract_requirements(model_id="m", prompt="p", inference_config=_CONFIG)
        )


def _reason(client: BedrockConverseClient, model: _Model) -> ReasoningOutcome:
    with client.reasoning_agent.override(model=FunctionModel(model)):
        return asyncio.run(
            client.generate_reasoning(model_id="m", prompt="p", inference_config=_CONFIG)
        )


def test_extraction_returns_typed_requirements(client: BedrockConverseClient) -> None:
    model = _Model(lambda _: _extraction())
    extracted = _extract(client, model)
    assert extracted.hard_requirements[0].value == "USD 50M"
    assert extracted.advisor_limits == AdvisorLimits(ticket_max=15_000_000.0)
    assert model.calls == 1


def test_non_usd_monetary_value_is_retried_once(client: BedrockConverseClient) -> None:
    model = _Model(lambda call: _extraction("AED 50M" if call == 1 else "USD 50M"))
    extracted = _extract(client, model)
    assert extracted.hard_requirements[0].value == "USD 50M"
    assert model.calls == 2
    assert "hard_requirements[0].value" in model.retry_prompts[0]
    assert "USD <amount>" in model.retry_prompts[0]


def test_non_usd_monetary_value_fails_closed_after_the_retry(
    client: BedrockConverseClient,
) -> None:
    model = _Model(lambda _: _extraction("AED 50M"))
    with pytest.raises(BedrockInvocationError):
        _extract(client, model)
    assert model.calls == 2


def test_schema_failure_raises_without_model_output(client: BedrockConverseClient) -> None:
    model = _Model(lambda _: {"strategic_thesis": _SECRET})
    with pytest.raises(BedrockInvocationError) as raised:
        _extract(client, model)
    assert _SECRET not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__
    assert model.calls == 2


def test_retries_a_throttled_call(client: BedrockConverseClient) -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise ModelHTTPError(
                429, "m", provider_error_code="ThrottlingException", body={"message": _SECRET}
            )
        return _extraction()

    model = _Model(respond)
    assert _extract(client, model).data_confidence == 0.6
    assert model.calls == 2


def test_non_transient_error_is_not_retried(client: BedrockConverseClient) -> None:
    def respond(_: int) -> JsonObject:
        raise ModelHTTPError(
            400, "m", provider_error_code="ValidationException", body={"message": _SECRET}
        )

    model = _Model(respond)
    with pytest.raises(BedrockInvocationError, match="ValidationException") as raised:
        _extract(client, model)
    assert _SECRET not in str(raised.value)
    assert model.calls == 1


def test_reasoning_returns_domain_narratives(client: BedrockConverseClient) -> None:
    candidate = {
        "seller_role_id": "s1",
        "why_it_matches": "a",
        "why_chosen_over_alternatives": "b",
        "recommended_pitch": "c",
        "risks_and_gaps": "d",
        "confidence_narrative": "e",
    }
    model = _Model(lambda _: {"candidates": [candidate]})
    outcome = _reason(client, model)
    assert [(c.seller_role_id, c.recommended_pitch) for c in outcome.candidates] == [("s1", "c")]
