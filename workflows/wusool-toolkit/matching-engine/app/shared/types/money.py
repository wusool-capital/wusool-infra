"""The one JSONB "money" shape shared across `buyer_roles` and `seller_roles`
columns (`ebitda_floor`, `check_size_min/max`, `ev_ceiling`, `est_revenue`,
`est_ebitda`, `owner_salary`, `valuation_low/mid/high`).

Shape confirmed from `database/sync-postgres.ps1`'s `money()` helper — not
guessed. The column itself may also be `NULL` entirely (no money object at
all); that's a separate, legitimate state from a `Money` with `amount=None`.
"""

import re
from typing import Literal

from pydantic import BaseModel, model_validator


class Money(BaseModel):
    amount: float | None = None
    currency: Literal["USD"] | None = None

    @model_validator(mode="after")
    def require_currency_for_amount(self) -> "Money":
        if self.amount is not None and self.currency is None:
            raise ValueError("a populated money amount must include currency=USD")
        return self


_USD_AMOUNT_RE = re.compile(r"^\s*USD\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([KMBkmb])?\s*$")


def parse_usd_amount(text: str | None) -> float | None:
    """Parse the strict monetary requirement format without FX conversion."""
    if text is None:
        return None
    match = _USD_AMOUNT_RE.fullmatch(text)
    if match is None:
        raise ValueError("monetary requirements must be written as USD <amount>")
    amount = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    return amount * {"": 1.0, "k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}[suffix]
