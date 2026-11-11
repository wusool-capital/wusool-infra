"""Provider-agnostic seam for transcript auto-correct. Implementations
return already-validated domain objects, so no raw JSON crosses this Port.
"""

from typing import Protocol

from app.modules.meetings.domain.corrections import CorrectionEdit


class CorrectorLLM(Protocol):
    async def suggest_corrections(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> list[CorrectionEdit]: ...
