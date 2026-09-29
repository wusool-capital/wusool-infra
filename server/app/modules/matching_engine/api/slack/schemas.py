"""Pydantic schemas for Slack payloads at the module boundary."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.matching_engine.domain.matching.deals import DealResolution


class DealChoiceValue(BaseModel):
    """The button value on the existing-deal prompt: which approval it
    resumes and how the approver wants the deal handled."""

    model_config = ConfigDict(frozen=True)

    match_result_id: uuid.UUID
    resolution: DealResolution
    existing_deal_id: str | None = None
