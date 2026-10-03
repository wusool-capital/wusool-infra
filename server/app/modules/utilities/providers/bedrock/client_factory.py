"""The one mechanical part of every module's own `boto_client.py` that was
genuinely byte-identical: the both-or-neither explicit-credentials check
and the `boto3.client("bedrock-runtime", ...)` call itself.

What deliberately stays per-module, per `utilities.domain.bedrock`'s own
docstring: each module reads its own `Settings` and its own `@lru_cache`
(a shared cache would need module-scoped keys for no real benefit), and a
module with its own `read_timeout`/`connect_timeout` requirement (see
`meetings`, `lead_magnets`) passes its own `Config` through `config=`
rather than this function inventing a policy for it.

Named args, not `**kwargs`, in the `boto3.client(...)` call below —
boto3-stubs resolves the right overload (and therefore the right return
type) by literal service name, which only works against an explicit
keyword call, not a dict unpack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from botocore.config import Config
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient


def build_bedrock_runtime_client(
    *,
    region_name: str,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    config: Config | None = None,
) -> BedrockRuntimeClient:
    """Uses the standard AWS credential provider chain (IAM role, ECS/EC2
    task role, local profile, env) unless explicit keys are passed.
    Passing only one of `access_key_id`/`secret_access_key` would make
    boto3 raise `PartialCredentialsError` at construction instead of
    falling back to the credential provider chain — both-or-neither.
    """
    has_explicit_keys = bool(access_key_id and secret_access_key)
    return boto3.client(
        "bedrock-runtime",
        region_name=region_name,
        aws_access_key_id=access_key_id if has_explicit_keys else None,
        aws_secret_access_key=secret_access_key if has_explicit_keys else None,
        config=config,
    )
