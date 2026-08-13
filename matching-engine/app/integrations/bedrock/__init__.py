"""AWS Bedrock integration boundary.

Provides a lazily-constructed client only. Buyer-requirement extraction and
match reasoning logic are not implemented in this phase — no `invoke_model`
call exists anywhere in this module.
"""

from .client import get_bedrock_runtime_client

__all__ = ["get_bedrock_runtime_client"]
