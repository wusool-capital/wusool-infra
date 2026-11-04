"""Public cross-module facade: only the seller-edit port `ddl_commands`
implements for saving web research. Everything else stays internal."""

from app.modules.matching_engine.application.ports.seller_edits import (
    SellerEditOutcome,
    SellerEditPort,
    SellerEditResult,
    SellerFieldEdit,
)

__all__ = [
    "SellerEditOutcome",
    "SellerEditPort",
    "SellerEditResult",
    "SellerFieldEdit",
]
