"""Bedrock Converse plumbing shared by every module that calls a model.

Extracted because three copies is where the drift starts: `meetings`' and
`matching_engine`'s clients each carried a byte-identical `_extract_json`
and transient-error set, and `meetings`' own docstring had to warn "if
you're fixing a bug in `_extract_json`/the retry policy here, check whether
`matching_engine`'s copy has the same bug" — an instruction that stops being
followable once a third caller exists.

Only the parts that are genuinely identical live here. What deliberately
stays per-module: the boto3 client factory (each reads its own `Settings`,
and `meetings` needs a 300s `read_timeout` where a user-facing caller wants
far less), the retry loop's shape, and the validation policy
(single-attempt-raise vs. validate-repair-retry). Those are real
behavioural differences, not duplication.

Framework-free by construction — `response` is typed as a `Mapping` rather
than botocore's `ConverseResponseTypeDef` so this module needs no
boto3/botocore import and stays honest `domain/` code (boto3-stubs is
dev-only and absent from the production image).
"""

import json
import re
from collections.abc import Mapping
from typing import Any

from app.modules.utilities.domain.json_types import JsonObject, JsonSchema

# Codes worth another attempt. Anything else is a bug, a bad request, or a
# permissions problem, and retrying it only burns latency.
TRANSIENT_ERROR_CODES = frozenset(
    {
        "ThrottlingException",
        "ServiceUnavailableException",
        "ModelTimeoutException",
        "InternalServerException",
    }
)


def converse_kwargs(
    *,
    model_id: str,
    prompt: str,
    output_schema: JsonSchema,
    max_tokens: int,
    temperature: float,
    system_prompt: str = "",
) -> dict[str, Any]:
    """Keyword arguments for one `bedrock-runtime.converse` call.

    `system` is omitted entirely when `system_prompt` is empty rather than
    sent as a blank block — that is what makes this one function serve both
    a caller that uses a system prompt and one that never has.
    """
    kwargs: dict[str, Any] = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        # Anthropic models reject `temperature` and `top_p` set together
        # (confirmed live: Bedrock raises ValidationException) — Anthropic's
        # own guidance is to tune one or the other, never both.
        "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
        "toolConfig": {
            "tools": [
                {
                    "toolSpec": {
                        "name": "return_structured_output",
                        "description": (
                            "Return the result as structured JSON matching the given schema."
                        ),
                        "inputSchema": {"json": output_schema},
                    }
                }
            ],
            # Forces the model to emit its answer as this tool's parsed JSON
            # input instead of free text — removes the root cause of the
            # markdown-fence/prose-wrapping failure mode entirely, rather
            # than recovering from it after the fact.
            "toolChoice": {"tool": {"name": "return_structured_output"}},
        },
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]
    return kwargs


def extract_json(response: Mapping[str, Any]) -> JsonObject:
    """Prefers the forced tool call's already-parsed JSON input. Falls back
    to text extraction only if a model/profile ignores the forced tool
    choice (confirmed live: some models routinely wrap JSON in a ```json
    fence and add prose commentary despite being forced via toolConfig) —
    best-effort recovery (direct parse, then fenced block, then the first
    balanced {...} substring).

    Returns `{}` on total failure rather than raising, deliberately: every
    caller already validates the result against a schema, so an empty dict
    fails that validation the same way a wrong-shaped-but-valid object
    would, instead of introducing a second error shape to handle. That
    includes a response missing the expected `output.message.content`
    shape entirely (a degraded-but-200 response, a stop-reason edge case)
    — a bare `KeyError` there would bypass every caller's schema-validation
    error handling instead of going through it.
    """
    output = response.get("output")
    message = output.get("message") if isinstance(output, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return {}

    for block in content:
        tool_use = block.get("toolUse")
        if tool_use and isinstance(tool_use.get("input"), dict):
            return tool_use["input"]

    text = "".join(block.get("text", "") for block in content).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    return {}
