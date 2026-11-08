"""Offline Bedrock for every module's client tests: a scripted Pydantic AI
model and the setup that keeps a client away from AWS and retry sleeps.
"""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import boto3
import pytest
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import RetryPromptPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.providers.bedrock import agent as agent_module

type Responder = Callable[[int], JsonObject]


class ScriptedModel:
    """Answers request N with `respond(N)` through the output tool, and
    records what each request carried."""

    def __init__(self, respond: Responder) -> None:
        self.respond = respond
        self.calls = 0
        self.retry_prompts: list[str] = []
        self.user_prompts: list[str] = []
        self.instructions: list[str | None] = []
        self.max_tokens: list[int | None] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.calls += 1
        self.instructions.append(info.instructions)
        self.max_tokens.append((info.model_settings or {}).get("max_tokens"))
        for part in messages[-1].parts:
            if isinstance(part, UserPromptPart):
                self.user_prompts.append(str(part.content))
            # A failed output check comes back as the output tool's return.
            elif isinstance(part, ToolReturnPart | RetryPromptPart):
                self.retry_prompts.append(str(part.content))
        args = self.respond(self.calls)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    @property
    def function_model(self) -> FunctionModel:
        return FunctionModel(self)


def offline_bedrock(monkeypatch: pytest.MonkeyPatch, client_module: ModuleType) -> None:
    """Give `client_module` a credential-free boto3 client and drop retry backoff."""
    monkeypatch.setattr(
        client_module,
        "get_bedrock_runtime_client",
        lambda: boto3.client("bedrock-runtime", region_name="eu-central-1"),
    )
    monkeypatch.setattr(agent_module, "_BASE_DELAY_SECONDS", 0.0)


def bedrock_error(code: str, *, status: int = 429, body: str = "") -> ModelHTTPError:
    """What Pydantic AI raises for a Bedrock `ClientError` with this code."""
    return ModelHTTPError(status, "m", provider_error_code=code, body={"message": body})
