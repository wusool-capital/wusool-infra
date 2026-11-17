"""The buyer and seller of every Deal."""

from typing import Protocol

from app.modules.interactions.domain.deals import DealParties


class DealPartiesPort(Protocol):
    async def load(self) -> tuple[DealParties, ...]:
        """Every live Deal with the Person or Organization on each side."""
        ...
