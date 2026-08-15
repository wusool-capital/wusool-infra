from functools import lru_cache
from typing import Any

import boto3

from app.config import get_settings


@lru_cache
def get_bedrock_runtime_client() -> Any:
    """Construction only — no `invoke_model` call in this phase.

    Uses the standard AWS credential provider chain (IAM role, ECS/EC2 task
    role, local profile, env) unless explicit keys are configured.
    """
    settings = get_settings()
    kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("bedrock-runtime", **kwargs)
