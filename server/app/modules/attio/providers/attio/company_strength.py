"""Typed reads of Attio's standard Companies and of workspace members, for the strength calibration.

The wire dicts are parsed into frozen models here, so nothing loose crosses into `interactions`.
"""

from pydantic import BaseModel, ConfigDict

from app.modules.attio.application.ports.client import AttioClientProtocol
from app.modules.attio.providers.attio.retry import post_with_retry
from app.modules.attio.providers.attio.values import actor, domains, first, record_id, vals

_PAGE_SIZE = 500


class CompanyStrength(BaseModel):
    """One Company with the connection strength Attio computed for it."""

    model_config = ConfigDict(frozen=True)

    record_id: str
    domains: tuple[str, ...]
    strength: str | None
    strongest_user_id: str | None


class WorkspaceMember(BaseModel):
    model_config = ConfigDict(frozen=True)

    member_id: str
    email: str


async def list_company_strengths(client: AttioClientProtocol) -> list[CompanyStrength]:
    """Every Company, paged serially by offset like the nightly resync."""
    companies: list[CompanyStrength] = []
    offset = 0
    while True:
        response = await post_with_retry(
            client,
            "/objects/companies/records/query",
            {"limit": _PAGE_SIZE, "offset": offset},
        )
        page = response.get("data", [])
        for record in page:
            values = vals(record)
            strength = first(values, "strongest_connection_strength")
            companies.append(
                CompanyStrength(
                    record_id=record_id(record),
                    domains=tuple(domains(values)),
                    strength=str(strength) if strength else None,
                    strongest_user_id=actor(values, "strongest_connection_user"),
                )
            )
        if len(page) < _PAGE_SIZE:
            return companies
        offset += _PAGE_SIZE


async def list_workspace_members(client: AttioClientProtocol) -> list[WorkspaceMember]:
    """Needs the `user_management:read` scope on the Attio key."""
    response = await client.get("/workspace_members")
    return [
        WorkspaceMember(member_id=item["id"]["workspace_member_id"], email=item["email_address"])
        for item in response.get("data", [])
    ]
