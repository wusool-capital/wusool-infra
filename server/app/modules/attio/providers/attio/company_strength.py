"""Typed reads of Attio's standard Companies and of workspace members, for the strength calibration.

The wire dicts are parsed into frozen models here, so nothing loose crosses into `interactions`.
"""

from pydantic import BaseModel, ConfigDict

from app.modules.attio.application.ports.client import AttioClientProtocol
from app.modules.attio.providers.attio.retry import get_with_retry, post_with_retry
from app.modules.attio.providers.attio.values import actor, first, raw_items, record_id, vals

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
    # By id, so a record seen on two pages because the data moved mid-read counts once.
    companies: dict[str, CompanyStrength] = {}
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
            company = CompanyStrength(
                record_id=record_id(record),
                # A Company can list several domains; `values.domains()` reads only the first.
                domains=tuple(
                    str(x["domain"]) for x in raw_items(values, "domains") if "domain" in x
                ),
                strength=str(strength) if strength else None,
                strongest_user_id=actor(values, "strongest_connection_user"),
            )
            companies[company.record_id] = company
        if len(page) < _PAGE_SIZE:
            return list(companies.values())
        offset += _PAGE_SIZE


async def list_workspace_members(client: AttioClientProtocol) -> list[WorkspaceMember]:
    """Needs the `user_management:read` scope on the Attio key."""
    response = await get_with_retry(client, "/workspace_members")
    return [
        WorkspaceMember(member_id=item["id"]["workspace_member_id"], email=item["email_address"])
        for item in response.get("data", [])
    ]
