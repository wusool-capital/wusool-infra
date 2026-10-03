"""Application-level exception types, one per concept until this file is
large enough to split. Vendor/provider-specific exceptions instead go in
`provider_errors.py`."""

from app.modules.matching_engine.domain.matching.deals import ExistingDeal


class RequirementExtractionError(Exception):
    """Raised when Bedrock's extraction output fails validation even after
    one bounded repair attempt (§7). The caller must not fabricate a profile
    or fall back to a stale one implicitly — fail closed (§8).
    """


class MatchReasoningError(Exception):
    """Raised when Bedrock's reasoning output fails validation even after
    one bounded repair attempt. The caller must not fabricate a narrative —
    fail the run rather than present an unreasoned match (§32.E).
    """


class DealGatewayError(Exception):
    """The Attio deal write or lookup failed; nothing was saved in Postgres."""


class ExistingDealsFoundError(Exception):
    """Attio already holds deal(s) for this buyer+seller pair — the approver
    must choose whether to promote one or create a new deal."""

    def __init__(self, deals: list[ExistingDeal]) -> None:
        self.deals = deals
        super().__init__(f"{len(deals)} existing deal(s) for this buyer/seller pair")


class PartialWriteError(Exception):
    """A write failed after an earlier step already landed. `landed` says
    what is already saved so the caller can tell the truth about it."""

    def __init__(self, landed: list[str], cause: Exception) -> None:
        self.landed = landed
        self.cause = cause
        super().__init__(str(cause))
