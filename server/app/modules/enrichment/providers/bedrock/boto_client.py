"""`@lru_cache`d boto3 Bedrock runtime client. Mirrors
`matching_engine.providers.bedrock.boto_client`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.modules.enrichment.config import get_settings
from app.modules.utilities.providers.bedrock.client_factory import build_bedrock_runtime_client

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient


@lru_cache
def get_bedrock_runtime_client() -> BedrockRuntimeClient:
    settings = get_settings()
    return build_bedrock_runtime_client(
        region_name=settings.aws_region,
        access_key_id=settings.aws_access_key_id,
        secret_access_key=settings.aws_secret_access_key,
    )
