from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from botocore.config import Config

from app.modules.meetings.config import get_settings
from app.modules.utilities.providers.bedrock.client_factory import build_bedrock_runtime_client

if TYPE_CHECKING:
    # boto3-stubs is a dev-only type-checking dependency (see pyproject.toml)
    # — never installed in the production image, so this import must stay
    # inside TYPE_CHECKING (and `from __future__ import annotations` above
    # keeps the return annotation below from being evaluated at runtime).
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

# botocore's own default read_timeout (60s) is too short for a whole-meeting
# summarization call — the merge/reduce pass can legitimately take longer
# than that to generate a long response, which timed out real production
# calls (see Scribe's app/ai/providers/bedrock/provider.py). This is the one
# reason this module owns its own client instead of sharing matching_engine's.
_CONVERSE_TIMEOUT_CONFIG = Config(connect_timeout=10, read_timeout=300)


@lru_cache
def get_bedrock_runtime_client() -> BedrockRuntimeClient:
    """Construction only — no `invoke_model` call in this phase."""
    settings = get_settings()
    return build_bedrock_runtime_client(
        region_name=settings.aws_region,
        access_key_id=settings.aws_access_key_id,
        secret_access_key=settings.aws_secret_access_key,
        config=_CONVERSE_TIMEOUT_CONFIG,
    )
