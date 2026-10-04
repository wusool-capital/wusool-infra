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
    # The match-results message to refresh, since the prompt itself is ephemeral.
    message_ts: str | None = None


class RunAnywayValue(BaseModel):
    """The button value on the discrepancy gate. Carries the advisor's context
    so "Run match anyway" applies it — otherwise the very context that
    triggered the conflict would be dropped from the run."""

    model_config = ConfigDict(frozen=True)

    buyer_role_id: str
    advisor_context: str | None = None


class DiscrepancyGateMetadata(BaseModel):
    """The discrepancy-gate modal's `private_metadata`: everything "Run anyway"
    needs to start the match once the buyer-selection modal is gone."""

    model_config = ConfigDict(frozen=True)

    buyer_role_id: str
    channel_id: str
    requested_by: str
    advisor_context: str | None = None
