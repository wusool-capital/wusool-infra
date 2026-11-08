"""`run_bedrock_agent`: transient retries, content-free errors, typed output."""

from __future__ import annotations

import asyncio
import logging

import pytest
from pydantic import BaseModel
from pydantic_ai.exceptions import ModelConnectionError, ModelTimeoutError

from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.providers.bedrock import agent as agent_module
from app.modules.utilities.providers.bedrock.agent import run_bedrock_agent, structured_agent
from app.modules.utilities.tests.bedrock_fakes import (
    Responder,
    ScriptedModel,
    bedrock_error,
)

_SECRET = "Khalid's floor is AED 42m"


class _Answer(BaseModel):
    value: int


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_module, "_BASE_DELAY_SECONDS", 0.0)


def _run(respond: Responder) -> tuple[_Answer, int]:
    model = ScriptedModel(respond)
    agent = structured_agent(_Answer, name="answer", output_retries=0)
    output = asyncio.run(
        run_bedrock_agent(
            lambda: agent.run("p", model=model.function_model), model_id="m", operation="test"
        )
    )
    return output, model.calls


def test_returns_validated_output() -> None:
    output, calls = _run(lambda _: {"value": 7})
    assert output == _Answer(value=7)
    assert calls == 1


def test_transient_error_is_retried_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise bedrock_error("ThrottlingException")
        return {"value": 1}

    with caplog.at_level(logging.WARNING):
        output, calls = _run(respond)
    assert output.value == 1
    assert calls == 2
    assert "error_code=ThrottlingException" in caplog.text


def test_connection_error_is_retried() -> None:
    def respond(call: int) -> JsonObject:
        if call == 1:
            raise ModelConnectionError("m", "connection reset")
        return {"value": 1}

    assert _run(respond)[1] == 2


def test_read_timeout_is_not_retried() -> None:
    calls = 0

    def respond(_: int) -> JsonObject:
        nonlocal calls
        calls += 1
        raise ModelTimeoutError("m", "read timed out")

    with pytest.raises(BedrockInvocationError, match="ModelTimeoutError"):
        _run(respond)
    assert calls == 1


def test_gives_up_after_three_attempts() -> None:
    def respond(_: int) -> JsonObject:
        raise bedrock_error("ServiceUnavailableException", status=503)

    with pytest.raises(BedrockInvocationError, match="ServiceUnavailableException"):
        _run(respond)


def test_non_transient_error_fails_without_content() -> None:
    def respond(_: int) -> JsonObject:
        raise bedrock_error("ValidationException", status=400, body=_SECRET)

    with pytest.raises(BedrockInvocationError) as raised:
        _run(respond)
    assert _SECRET not in str(raised.value)
    assert raised.value.__cause__ is None


def test_invalid_output_fails_without_content() -> None:
    with pytest.raises(BedrockInvocationError, match="output failed validation") as raised:
        _run(lambda _: {"value": _SECRET})
    assert _SECRET not in str(raised.value)
    assert raised.value.__suppress_context__
