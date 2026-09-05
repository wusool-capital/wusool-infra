"""Provider/vendor-specific exception types shared across modules — one per
provider, in this one file until it's large enough to split by vendor.

Kept separate from `domain/errors.py`'s `AppError` hierarchy on purpose:
`AppError` subclasses carry an HTTP status code and are meant to reach
`register_exception_handlers` and become a response — a provider-invocation
failure must never reach that boundary un-translated (fabricating a 500 for
"the LLM call failed" tells the caller nothing useful). Each application
service that calls a provider catches this instead and converts it into its
own domain-facing error (or, for a background task with no request to
answer, records the failure on its own row and logs it).
"""


class BedrockInvocationError(Exception):
    """Raised after exhausting retries, or for a non-transient failure. The
    caller must not fabricate output in response — fail closed.
    """
