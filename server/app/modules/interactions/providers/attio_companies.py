"""Implements `StrengthSourcePort` by reading Attio's Companies and workspace members."""

from collections.abc import Sequence

from app.modules.attio import (
    AttioClientProtocol,
    list_company_strengths,
    list_workspace_members,
)
from app.modules.interactions.domain.addresses import team_member_of
from app.modules.interactions.domain.calibration import CompanyInput, parse_label


class AttioStrengthSource:
    def __init__(self, client: AttioClientProtocol, internal_domains: tuple[str, ...]) -> None:
        self._client = client
        self._internal_domains = internal_domains

    async def companies(self) -> Sequence[CompanyInput]:
        members = await list_workspace_members(self._client)
        address_of = {
            m.member_id: team_member_of(m.email.strip().lower(), self._internal_domains)
            for m in members
        }
        return [
            CompanyInput(
                record_id=company.record_id,
                domains=company.domains,
                attio_label=parse_label(company.strength),
                raw_label=company.strength,
                strongest_user=address_of.get(company.strongest_user_id or ""),
            )
            for company in await list_company_strengths(self._client)
        ]
