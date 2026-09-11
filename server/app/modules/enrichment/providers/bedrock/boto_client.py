"""`@lru_cache`d boto3 Bedrock runtime client. Mirrors
`matching_engine.providers.bedrock.boto_client`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3

from app.modules.enrichment.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient


@lru_cache
def get_bedrock_runtime_client() -> BedrockRuntimeClient:
    settings = get_settings()
    # Both-or-neither: passing only one of the pair makes boto3 raise
    # PartialCredentialsError at construction instead of falling back to
    # the credential provider chain.
    has_explicit_keys = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id if has_explicit_keys else None,
        aws_secret_access_key=settings.aws_secret_access_key if has_explicit_keys else None,
    )
