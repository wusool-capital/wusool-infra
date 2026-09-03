"""Application-level exception types, one per concept until this file is
large enough to split. Vendor/provider-specific exceptions instead go in
`provider_errors.py`."""


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
