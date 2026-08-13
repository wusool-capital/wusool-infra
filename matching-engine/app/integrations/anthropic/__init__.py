"""Anthropic integration boundary.

Provides a lazily-constructed client only. Buyer-requirement extraction and
match reasoning logic are not implemented in this phase.
"""

from .client import get_anthropic_client

__all__ = ["get_anthropic_client"]
