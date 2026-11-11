"""`BedrockConverseClient` on Pydantic AI, driven by `FunctionModel` — no AWS."""

from __future__ import annotations

import asyncio

import pytest

from app.modules.enrichment.domain.proposals import ExtractedField
from app.modules.enrichment.providers.bedrock import client as client_module
from app.modules.enrichment.providers.bedrock.client import BedrockConverseClient
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.tests.bedrock_fakes import ScriptedModel, bedrock_error, offline_bedrock

_SECRET = "Acme's revenue is AED 42m"

_FIELD: JsonObject = {
    "field_name": "est_revenue",
    "value": "5000000",
    "source_url": "https://example.com",
    "confidence": "high",
    "rationale": "press release",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> BedrockConverseClient:
    offline_bedrock(monkeypatch, client_module)
    return BedrockConverseClient()


def _extract(client: BedrockConverseClient, model: ScriptedModel) -> tuple[ExtractedField, ...]:
    with client.agent.override(model=model.function_model):
        return asyncio.run(
            client.extract_fields(model_id="m", prompt="p", temperature=0.0, max_tokens=100)
        )


def test_returns_typed_domain_fields(client: BedrockConverseClient) -> None:
    model = ScriptedModel(lambda _: {"fields": [_FIELD]})
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
    model = ScriptedModel(lambda call: {"fields": [bad if call == 1 else _FIELD]})
    fields = _extract(client, model)
    assert fields[0].confidence == "high"
    assert model.calls == 2
    assert "confidence" in model.retry_prompts[0]


def test_schema_failure_twice_raises_without_model_output(client: BedrockConverseClient) -> None:
    model = ScriptedModel(lambda _: {"fields": [{"field_name": _SECRET}]})
    with pytest.raises(BedrockInvocationError) as raised:
        _extract(client, model)
    assert _SECRET not in str(raised.value)
    assert raised.value.__cause__ is None
    assert model.calls == 2


def test_retries_a_throttled_call(client: BedrockConverseClient) -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise bedrock_error("ThrottlingException", body=_SECRET)
        return {"fields": [_FIELD]}

    model = ScriptedModel(respond)
    assert len(_extract(client, model)) == 1
    assert model.calls == 2
