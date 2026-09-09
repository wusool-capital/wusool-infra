"""`extract_json` recovery, per real observed Bedrock behavior: models
routinely wrap JSON in a ```json fence and add prose commentary before/after
it despite being asked for strict JSON. No AWS calls — these construct the
`converse` response shape directly.

Lived at `matching_engine/tests/unit/test_bedrock_converse_client.py` until
the function it covers moved here, shared by every module that calls a model.
`converse_kwargs`' one branch is covered at the bottom.
"""

from app.modules.utilities.domain.bedrock import converse_kwargs, extract_json


def _response(text: str) -> dict:
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}}


def _tool_use_response(input_dict: dict) -> dict:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"toolUse": {"name": "return_structured_output", "input": input_dict}}],
            }
        }
    }


def test_prefers_tool_use_input_over_text() -> None:
    """The forced-tool-call path (§ toolConfig) returns already-parsed JSON —
    preferred over any text block, and never re-parsed as a string."""
    result = extract_json(_tool_use_response({"a": 1}))
    assert result == {"a": 1}


def test_extracts_plain_json() -> None:
    result = extract_json(_response('{"a": 1}'))
    assert result == {"a": 1}


def test_extracts_json_wrapped_in_markdown_fence() -> None:
    """Reproduces the exact real Bedrock output shape observed live."""
    text = (
        '```json\n{\n  "hard_requirements": [],\n  "data_confidence": 0.4\n}\n```\n\n'
        "**Confidence note:** The provided information is minimal."
    )
    result = extract_json(_response(text))
    assert result == {"hard_requirements": [], "data_confidence": 0.4}


def test_extracts_json_with_leading_and_trailing_prose_no_fence() -> None:
    text = 'Sure, here is the JSON:\n{"a": 1, "b": [1, 2]}\nLet me know if you need anything else.'
    result = extract_json(_response(text))
    assert result == {"a": 1, "b": [1, 2]}


def test_returns_empty_dict_when_nothing_parseable() -> None:
    """Fails closed into Pydantic validation failure (§7's repair-retry),
    rather than raising a second, differently-shaped error here."""
    result = extract_json(_response("I cannot help with that request."))
    assert result == {}


def test_returns_empty_dict_for_empty_text() -> None:
    result = extract_json(_response(""))
    assert result == {}


def test_converse_kwargs_omits_system_when_no_system_prompt() -> None:
    """An empty system prompt must drop the block entirely, not send a blank
    one — that branch is what lets one function serve both callers."""
    kwargs = converse_kwargs(
        model_id="m", prompt="p", output_schema={}, max_tokens=10, temperature=0.2
    )
    assert "system" not in kwargs
    assert kwargs["toolConfig"]["toolChoice"] == {"tool": {"name": "return_structured_output"}}


def test_converse_kwargs_includes_system_when_given() -> None:
    kwargs = converse_kwargs(
        model_id="m",
        prompt="p",
        output_schema={},
        max_tokens=10,
        temperature=0.2,
        system_prompt="s",
    )
    assert kwargs["system"] == [{"text": "s"}]
