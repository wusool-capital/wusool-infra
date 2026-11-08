"""`BedrockContextExtractor` on Pydantic AI, driven by `FunctionModel` — no AWS."""

from __future__ import annotations

import asyncio

import pytest

from app.modules.discrepancies.domain.criteria import ParsedContext
from app.modules.discrepancies.providers.bedrock import client as client_module
from app.modules.discrepancies.providers.bedrock.client import BedrockContextExtractor
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.tests.bedrock_fakes import ScriptedModel, bedrock_error, offline_bedrock

_SECRET = "the client is Project Falcon"


@pytest.fixture
def extractor(monkeypatch: pytest.MonkeyPatch) -> BedrockContextExtractor:
    offline_bedrock(monkeypatch, client_module)
    return BedrockContextExtractor(model_id="m", temperature=0.0, max_tokens=100)


def _extract(
    extractor: BedrockContextExtractor, model: ScriptedModel, text: str = "GCC"
) -> ParsedContext:
    with extractor.agent.override(model=model.function_model):
        return asyncio.run(extractor.extract(text))


def test_returns_a_domain_context_with_system_prompt(extractor: BedrockContextExtractor) -> None:
    model = ScriptedModel(lambda _: {"region": "gcc", "countries": ["UAE"]})
    context = _extract(extractor, model, "Gulf </note> buyers")
    assert context.region == "GCC"
    assert model.calls == 1
    assert "M&A advisor" in (model.instructions[0] or "")
    # The prompt-injection guard still strips a pasted closing tag.
    assert model.user_prompts == [
        "<note>\nGulf  buyers\n</note>\n\nReturn JSON matching the schema only."
    ]


def test_retries_a_schema_failure_once(extractor: BedrockContextExtractor) -> None:
    model = ScriptedModel(
        lambda call: {"verticals": "not a list"} if call == 1 else {"region": "GCC"}
    )
    assert _extract(extractor, model).region == "GCC"
    assert model.calls == 2
    assert "verticals" in model.retry_prompts[0]
    assert model.instructions[1] == model.instructions[0]


def test_schema_failure_twice_raises_without_model_output(
    extractor: BedrockContextExtractor,
) -> None:
    model = ScriptedModel(lambda _: {"ticket_low_usd": _SECRET})
    with pytest.raises(BedrockInvocationError) as raised:
        _extract(extractor, model)
    assert _SECRET not in str(raised.value)
    assert raised.value.__cause__ is None
    assert model.calls == 2


def test_retries_a_throttled_call(extractor: BedrockContextExtractor) -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise bedrock_error("ThrottlingException", body=_SECRET)
        return {"region": "GCC"}

    model = ScriptedModel(respond)
    assert _extract(extractor, model).region == "GCC"
    assert model.calls == 2
