"""The provider-agnostic seam application services depend on. Callers import
this Protocol, never `boto3`, `pydantic_ai` or
`app.modules.meetings.providers.bedrock` directly — swapping providers later
means writing a new implementation of this Protocol, not touching the
application layer.

Returns an already-validated domain `MeetingSummary`, so no raw JSON or
Pydantic schema crosses this Port.
"""

from typing import Protocol

from app.modules.meetings.domain.summary import MeetingSummary


class SummarizerLLM(Protocol):
    async def summarize(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        check_limits: bool,
    ) -> MeetingSummary: ...
