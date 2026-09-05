"""The provider-agnostic seam application services depend on. Callers import
this Protocol, never `boto3` or `app.modules.meetings.providers.bedrock`
directly — swapping providers later means writing a new implementation of
this Protocol, not touching the application layer.

Returns a plain, already-validated `dict` — never a Pydantic schema, which
must not cross this Port.
"""

from typing import Protocol

from app.modules.utilities.domain.json_types import JsonObject


class SummarizerLLM(Protocol):
    async def summarize(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> JsonObject: ...
