"""Pydantic models for this module's own Slack payload state — parsed at the
handler boundary so raw JSON never reaches the use case.
"""

from pydantic import BaseModel, ConfigDict


class CheckBuyerModalMetadata(BaseModel):
    """The buyer-picker modal's `private_metadata`."""

    model_config = ConfigDict(frozen=True)

    channel_id: str
