"""Ticket-band fit — scored, never used to eliminate. A buyer's cheque can buy
a partial stake in a company valued above it, so a mismatch is a weak signal
that lowers the score rather than a fact that rules a seller out.
"""

from dataclasses import dataclass

from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.sellers import SellerCandidate


@dataclass(frozen=True)
class TicketBand:
    minimum: float | None
    maximum: float | None

    @classmethod
    def from_buyer(cls, buyer: BuyerContext) -> "TicketBand | None":
        minimum = buyer.check_size_min.amount if buyer.check_size_min else None
        maximum = buyer.check_size_max.amount if buyer.check_size_max else None
        return cls(minimum, maximum) if minimum is not None or maximum is not None else None

    def fit(self, seller: SellerCandidate) -> tuple[str, bool]:
        """Returns `(result, seller_has_valuation)`. Fails only when the
        seller's whole valuation range lies outside the band."""
        mid = seller.valuation_mid.amount if seller.valuation_mid else None
        low = seller.valuation_low.amount if seller.valuation_low else mid
        high = seller.valuation_high.amount if seller.valuation_high else mid
        if low is None and high is None:
            return "Unknown", False
        too_large = self.maximum is not None and low is not None and low > self.maximum
        too_small = self.minimum is not None and high is not None and high < self.minimum
        return ("Fail" if too_large or too_small else "Pass"), True
