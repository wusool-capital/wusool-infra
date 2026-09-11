"""The `bedrock-runtime` client for the lead-magnet tools.

No credential arguments, deliberately: Bedrock is reached through the
instance's own IAM role in both environments
(`infrastructure/terraform/modules/bedrock-access`), so boto3's default
credential chain is the whole story and there is nowhere for a key to live.
That is the point of the migration — the exposed key does not get protected,
it stops existing.

`read_timeout` is 120s, not `meetings`' 300s: a visitor is waiting on these
calls, so a hung request should fail fast enough for the fallback to still
feel like a result. Botocore's 60s default is the wrong end of that trade —
it already broke a production summarization call once.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from app.modules.lead_magnets.config import get_settings

if TYPE_CHECKING:
    # boto3-stubs is dev-only (see pyproject.toml) and never installed in
    # the production image, so this import must stay under TYPE_CHECKING.
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

_CONVERSE_TIMEOUT_CONFIG = Config(connect_timeout=10, read_timeout=120)


@lru_cache
def get_bedrock_runtime_client() -> "BedrockRuntimeClient":
    return boto3.client(
        "bedrock-runtime",
        region_name=get_settings().aws_region,
        config=_CONVERSE_TIMEOUT_CONFIG,
    )
