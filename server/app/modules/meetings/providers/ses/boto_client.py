from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3

from app.modules.meetings.config import get_settings

if TYPE_CHECKING:
    # boto3-stubs is a dev-only type-checking dependency (see pyproject.toml)
    # — never installed in the production image, so this import must stay
    # inside TYPE_CHECKING (and `from __future__ import annotations` above
    # keeps the return annotation below from being evaluated at runtime).
    from mypy_boto3_ses import SESClient


@lru_cache
def get_ses_client() -> SESClient:
    """Construction only -- no `send_email` call in this phase.

    Uses the standard AWS credential provider chain (IAM role, ECS/EC2 task
    role, local profile, env) unless explicit keys are configured -- same
    pattern as `providers.bedrock.boto_client.get_bedrock_runtime_client`.
    """
    settings = get_settings()
    has_explicit_keys = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
    return boto3.client(
        "ses",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id if has_explicit_keys else None,
        aws_secret_access_key=settings.aws_secret_access_key if has_explicit_keys else None,
    )
