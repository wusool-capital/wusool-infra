"""Promoted out of `matching_engine` (AZM-92/WP3) so a buyer's data quality
can be asked about on its own — via its own standalone `/check-buyer`
command — not just inside `/find-match`. Deliberately never imports
`matching_engine.domain.matching.scoring.CRITERION_REGISTRY`, which mixes
in seller-only criteria (`outreach_tier`, `appetite_signal`) this module
has no business touching; it defines its own small, buyer-facing
vocabulary instead (`domain/vocabulary.py`).

Keeps the module-dependency graph acyclic by construction: this module
reads buyer criteria through `BuyerCriteriaReaderPort`, implemented by
`matching_engine` and wired at startup by `server/main.py` — the same
shape `discovery.SellerDraftPort` already uses for its own reverse
hand-off. `discrepancies` never imports `matching_engine`.

Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here.
"""

from app.modules.discrepancies.api.dependencies import (
    check_buyer_discrepancies,
    configure_criteria_reader_port,
)
from app.modules.discrepancies.api.slack.views.report import build_discrepancy_blocks
from app.modules.discrepancies.application.check import DiscrepancyCheckResult
from app.modules.discrepancies.application.ports.criteria_reader import BuyerCriteriaReaderPort
from app.modules.discrepancies.domain.criteria import BuyerCriteria, DiscrepancyReport

__all__ = [
    "BuyerCriteria",
    "BuyerCriteriaReaderPort",
    "DiscrepancyCheckResult",
    "DiscrepancyReport",
    "build_discrepancy_blocks",
    "check_buyer_discrepancies",
    "configure_criteria_reader_port",
]
