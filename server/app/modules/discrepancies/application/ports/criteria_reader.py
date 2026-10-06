"""The read-only seam this module depends on instead of owning a database
connection — `matching_engine` implements it (§ `providers/discrepancies/
criteria_reader_adapter.py`) by wrapping its own buyer resolution, so
`/check-buyer` and `/find-match` search the same buyers by the same rules
with no second copy of that logic. Mirrors `discovery.SellerDraftPort`.
"""

from typing import Protocol

from app.modules.discrepancies.domain.criteria import BuyerCriteria


class BuyerCriteriaReaderPort(Protocol):
    async def search(self, name: str) -> list[BuyerCriteria]: ...
    async def get(self, buyer_role_id: str) -> BuyerCriteria | None: ...
