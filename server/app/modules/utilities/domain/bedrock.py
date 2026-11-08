"""Bedrock error codes shared by every module that calls a model.

Request building, response parsing and validation now belong to Pydantic AI
(see `utilities.providers.bedrock.agent`). What stays here is the one policy
decision that is ours: which AWS error codes are worth another attempt.

Framework-free by construction, so `domain/` code can import it without
pulling in boto3 or pydantic_ai.
"""

# Codes worth another attempt. Anything else is a bug, a bad request, or a
# permissions problem, and retrying it only burns latency.
TRANSIENT_ERROR_CODES = frozenset(
    {
        "ThrottlingException",
        "ServiceUnavailableException",
        "ModelTimeoutException",
        "InternalServerException",
    }
)
