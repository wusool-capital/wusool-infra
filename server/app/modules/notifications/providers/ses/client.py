"""One shared SES client per credential set -- not a full Bedrock/Slack-
style module-owned singleton, since `notifications` has no config of its
own (see `providers/slack/client.py`'s docstring: "the token is passed in,
never imported from one specific module's config"). Every argument is
hashable, so `lru_cache` still dedupes callers that pass the same
region/keys.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    # boto3-stubs is a dev-only type-checking dependency (see
    # server/pyproject.toml) -- never installed in the production image,
    # so this import must stay inside TYPE_CHECKING (and `from __future__
    # import annotations` above keeps the return annotation below from
    # being evaluated at runtime).
    from mypy_boto3_ses import SESClient


@lru_cache
def get_ses_client(
    *,
    region_name: str,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
) -> SESClient:
    """Construction only -- no `send_email` call in this phase.

    Uses the standard AWS credential provider chain (IAM role, ECS/EC2
    task role, local profile, env) unless explicit keys are passed.
    """
    has_explicit_keys = bool(aws_access_key_id and aws_secret_access_key)
    return boto3.client(
        "ses",
        region_name=region_name,
        aws_access_key_id=aws_access_key_id if has_explicit_keys else None,
        aws_secret_access_key=aws_secret_access_key if has_explicit_keys else None,
    )
