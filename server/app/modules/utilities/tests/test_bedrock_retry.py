"""`invoke_bedrock_with_retry` — the retry/logging scaffolding that used to
be duplicated near-verbatim in `enrichment`'s and `lead_magnets`' own
Bedrock clients. No real AWS calls: `converse` is a plain callable the test
controls.
"""

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.providers.bedrock.retry import invoke_bedrock_with_retry


def _converse_response(input_dict: dict) -> dict:
    return {
        "output": {
            "message": {
                "content": [{"toolUse": {"input": input_dict}}],
            }
        },
        "usage": {"inputTokens": 10, "outputTokens": 5},
    }


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "boom"}}, "Converse")


async def test_returns_extracted_json_on_first_success() -> None:
    calls = 0

    def converse() -> dict:
        nonlocal calls
        calls += 1
        return _converse_response({"a": 1})

    result = await invoke_bedrock_with_retry(
        converse=converse, model_id="test-model", operation="test_op", base_delay_seconds=0
    )

    assert result == {"a": 1}
    assert calls == 1


async def test_retries_a_transient_client_error_then_succeeds() -> None:
    calls = 0

    def converse() -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _client_error("ThrottlingException")
        return _converse_response({"a": 2})

    result = await invoke_bedrock_with_retry(
        converse=converse, model_id="test-model", operation="test_op", base_delay_seconds=0
    )

    assert result == {"a": 2}
    assert calls == 2


async def test_retries_a_connection_error() -> None:
    calls = 0

    def converse() -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise EndpointConnectionError(endpoint_url="https://bedrock.example.com")
        return _converse_response({"a": 3})

    result = await invoke_bedrock_with_retry(
        converse=converse, model_id="test-model", operation="test_op", base_delay_seconds=0
    )

    assert result == {"a": 3}
    assert calls == 2


async def test_does_not_retry_a_non_transient_client_error() -> None:
    calls = 0

    def converse() -> dict:
        nonlocal calls
        calls += 1
        raise _client_error("ValidationException")

    with pytest.raises(BedrockInvocationError):
        await invoke_bedrock_with_retry(
            converse=converse,
            model_id="test-model",
            operation="test_op",
            base_delay_seconds=0,
        )

    assert calls == 1


async def test_raises_bedrock_invocation_error_after_exhausting_attempts() -> None:
    calls = 0

    def converse() -> dict:
        nonlocal calls
        calls += 1
        raise _client_error("ThrottlingException")

    with pytest.raises(BedrockInvocationError):
        await invoke_bedrock_with_retry(
            converse=converse,
            model_id="test-model",
            operation="test_op",
            max_attempts=2,
            base_delay_seconds=0,
        )

    assert calls == 2
