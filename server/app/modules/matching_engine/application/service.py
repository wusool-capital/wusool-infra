"""Compose matching_engine application use cases behind one module facade.

`application/requirements.py`'s `BuyerRequirementExtractionService` and
`matching/reasoning_service.py`'s `MatchReasoningService` stay outside this
facade — they're collaborator objects `MatchingMixin.run_match` calls
internally, not concerns anything else in this module calls directly (see
`bootstrap.py` for how they're assembled and handed to `ServiceBase`).
"""

from app.modules.matching_engine.application.approvals import ApprovalsMixin
from app.modules.matching_engine.application.buyers import BuyersMixin
from app.modules.matching_engine.application.matching.use_cases import MatchingMixin
from app.modules.matching_engine.application.web_search import WebSearchMixin


class MatchingEngineService(ApprovalsMixin, BuyersMixin, MatchingMixin, WebSearchMixin):
    """No business logic of its own — combines every concern mixin above
    into one composed class. Add a new use-case area as its own
    `ServiceBase` mixin and list it here, rather than growing this class or
    a mixin file directly.
    """
