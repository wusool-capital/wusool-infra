"""Shared Pydantic DTOs used across more than one concept's own `api/<concept>.py`."""

from pydantic import BaseModel


class OrganizationSummary(BaseModel):
    """Slim organization view embedded in both buyer and seller schemas.
    Deliberately duplicated in `ddl_commands/api/schemas.py`, not shared —
    a plain presentation DTO, not cross-cutting logic.
    """

    model_config = {"from_attributes": True}

    attio_id: str
    name: str
    hq_country: str | None = None
    geographic_focus: list[str] = []
    sector_focus: list[str] = []
    relationship_status: str | None = None
