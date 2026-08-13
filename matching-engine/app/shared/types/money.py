"""The one JSONB "money" shape shared across `buyer_roles` and `seller_roles`
columns (`ebitda_floor`, `check_size_min/max`, `ev_ceiling`, `est_revenue`,
`est_ebitda`, `owner_salary`, `valuation_low/mid/high`).

Shape confirmed from `scripts/db/sync-postgres.ps1`'s `money()` helper — not
guessed. The column itself may also be `NULL` entirely (no money object at
all); that's a separate, legitimate state from a `Money` with `amount=None`.
"""

from pydantic import BaseModel


class Money(BaseModel):
    amount: float | None = None
    currency: str | None = None
