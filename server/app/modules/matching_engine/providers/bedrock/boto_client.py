from functools import lru_cache

import boto3
from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

from app.modules.matching_engine.config import get_settings


@lru_cache
def get_bedrock_runtime_client() -> BedrockRuntimeClient:
    """Construction only — no `invoke_model` call in this phase.

    Uses the standard AWS credential provider chain (IAM role, ECS/EC2 task
    role, local profile, env) unless explicit keys are configured.
    """
    settings = get_settings()
    # Both-or-neither: passing only one of the pair makes boto3 raise
    # PartialCredentialsError at construction instead of falling back to
    # the credential provider chain.
    has_explicit_keys = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
    # Named args, not **kwargs — boto3-stubs resolves the right overload
    # (and therefore the right return type) by literal service name, which
    # only works against an explicit keyword call, not a dict unpack.
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id if has_explicit_keys else None,
        aws_secret_access_key=settings.aws_secret_access_key if has_explicit_keys else None,
    )
