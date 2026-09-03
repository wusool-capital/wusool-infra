"""AWS Bedrock's Converse API response envelope — a fixed, documented AWS
API contract (not a boto3-stubs concern; those type the full client
surface, this types only the one operation actually called). `BaseClient`
itself stays untyped (`get_bedrock_runtime_client() -> Any`) since
`boto3.client("bedrock-runtime")` can't be typed from a string literal
without the stub package — `BedrockRuntimeClient` below is a narrow
`Protocol` covering only the `converse` method this codebase calls.
"""

from typing import Any, Protocol, TypedDict

from app.modules.utilities.domain.json_types import JsonObject


class ConverseToolUse(TypedDict):
    toolUseId: str
    name: str
    input: JsonObject


class ConverseContentBlock(TypedDict, total=False):
    text: str
    toolUse: ConverseToolUse


class ConverseMessage(TypedDict):
    role: str
    content: list[ConverseContentBlock]


class ConverseOutput(TypedDict):
    message: ConverseMessage


class ConverseUsage(TypedDict, total=False):
    inputTokens: int
    outputTokens: int
    totalTokens: int


class ConverseResponse(TypedDict, total=False):
    output: ConverseOutput
    stopReason: str
    usage: ConverseUsage


class BedrockRuntimeClient(Protocol):
    def converse(
        self,
        *,
        modelId: str,
        messages: list[dict[str, Any]],
        inferenceConfig: dict[str, Any],
        toolConfig: dict[str, Any],
    ) -> ConverseResponse: ...
