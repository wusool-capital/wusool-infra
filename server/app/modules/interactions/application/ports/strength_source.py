"""The Companies and connection strengths Attio computed, the baseline we calibrate against."""

from collections.abc import Sequence
from typing import Protocol

from app.modules.interactions.domain.calibration import CompanyInput


class StrengthSourcePort(Protocol):
    async def companies(self) -> Sequence[CompanyInput]:
        """Every Company with Attio's label and the address of its strongest user."""
        ...
