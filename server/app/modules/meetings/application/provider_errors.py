"""Provider/vendor-specific exception types, one per provider, in this one
file until it's large enough to split by vendor."""


class BedrockInvocationError(Exception):
    """Raised after exhausting retries, or for a non-transient failure. The
    caller must not fabricate output in response — fail closed.
    """
