"""The provider-agnostic seam `EnrichMixin` depends on for turning source
material into field proposals. Each implementation owns its own
validate-retry-then-fail-closed policy internally and returns
already-validated domain `ExtractedField`s — never the Pydantic schema
itself, which must not cross this Port.
"""

from typing import Protocol

from app.modules.enrichment.domain.proposals import ExtractedField


class ExtractionClient(Protocol):
    async def extract_fields(
        self,
        *,
        model_id: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[ExtractedField, ...]: ...
