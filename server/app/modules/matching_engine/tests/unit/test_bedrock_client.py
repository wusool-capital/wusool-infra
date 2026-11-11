"""`BedrockConverseClient` on Pydantic AI, driven by `FunctionModel` — no AWS."""

from __future__ import annotations

import asyncio

import pytest

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
from app.modules.utilities.tests.bedrock_fakes import ScriptedModel, bedrock_error, offline_bedrock

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


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> BedrockConverseClient:
    offline_bedrock(monkeypatch, client_module)
    return BedrockConverseClient()


def _extract(client: BedrockConverseClient, model: ScriptedModel) -> ExtractedRequirements:
    with client.extraction_agent.override(model=model.function_model):
        return asyncio.run(
            client.extract_requirements(model_id="m", prompt="p", inference_config=_CONFIG)
        )


def _reason(client: BedrockConverseClient, model: ScriptedModel) -> ReasoningOutcome:
    with client.reasoning_agent.override(model=model.function_model):
        return asyncio.run(
            client.generate_reasoning(model_id="m", prompt="p", inference_config=_CONFIG)
        )


def test_extraction_returns_typed_requirements(client: BedrockConverseClient) -> None:
    model = ScriptedModel(lambda _: _extraction())
    extracted = _extract(client, model)
    assert extracted.hard_requirements[0].value == "USD 50M"
    assert extracted.advisor_limits == AdvisorLimits(ticket_max=15_000_000.0)
    assert model.calls == 1


def test_non_usd_monetary_value_is_retried_once(client: BedrockConverseClient) -> None:
    model = ScriptedModel(lambda call: _extraction("AED 50M" if call == 1 else "USD 50M"))
    extracted = _extract(client, model)
    assert extracted.hard_requirements[0].value == "USD 50M"
    assert model.calls == 2
    assert "hard_requirements[0].value" in model.retry_prompts[0]
    assert "USD <amount>" in model.retry_prompts[0]


def test_non_usd_monetary_value_fails_closed_after_the_retry(
    client: BedrockConverseClient,
) -> None:
    model = ScriptedModel(lambda _: _extraction("AED 50M"))
    with pytest.raises(BedrockInvocationError):
        _extract(client, model)
    assert model.calls == 2


def test_schema_failure_raises_without_model_output(client: BedrockConverseClient) -> None:
    model = ScriptedModel(lambda _: {"strategic_thesis": _SECRET})
    with pytest.raises(BedrockInvocationError) as raised:
        _extract(client, model)
    assert _SECRET not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__
    assert model.calls == 2


def test_retries_a_throttled_call(client: BedrockConverseClient) -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise bedrock_error("ThrottlingException", body=_SECRET)
        return _extraction()

    model = ScriptedModel(respond)
    assert _extract(client, model).data_confidence == 0.6
    assert model.calls == 2


def test_non_transient_error_is_not_retried(client: BedrockConverseClient) -> None:
    def respond(_: int) -> JsonObject:
        raise bedrock_error("ValidationException", status=400, body=_SECRET)

    model = ScriptedModel(respond)
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
    model = ScriptedModel(lambda _: {"candidates": [candidate]})
    outcome = _reason(client, model)
    assert [(c.seller_role_id, c.recommended_pitch) for c in outcome.candidates] == [("s1", "c")]
