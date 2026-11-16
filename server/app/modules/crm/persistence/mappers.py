"""ORM rows to the CRM's domain values. Nothing here queries."""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Literal

from pydantic import BaseModel, JsonValue, StrictFloat, StrictInt, ValidationError

from app.models import BuyerRole as BuyerRoleRow
from app.models import Organization
from app.models import Person as PersonRow
from app.models import SellerRole as SellerRoleRow
from app.modules.crm.domain.roles import BuyerRole, Person, SellerRole, open_to_selling


class _Money(BaseModel):
    """The `{amount, currency}` blob Attio money fields are stored as."""

    amount: StrictInt | StrictFloat | None = None


def amount(value: Mapping[str, JsonValue] | None) -> float | None:
    """A malformed blob reads as unknown, so one bad row never fails a page."""
    try:
        parsed = _Money.model_validate(value or {})
    except ValidationError:
        return None
    return None if parsed.amount is None else float(parsed.amount)


def first_email(emails: Sequence[str]) -> str | None:
    return emails[0] if emails else None


def to_buyer(role: BuyerRoleRow, org: Organization) -> BuyerRole:
    return BuyerRole(
        id=str(role.id),
        name=org.name,
        hq=org.hq_country,
        website=org.domains[0] if org.domains else None,
        sectors=(role.target_vertical,) if role.target_vertical else (),
        geographies=tuple(dict.fromkeys([*role.target_region, *role.target_country])),
        check_size_min_usd=amount(role.check_size_min),
        check_size_max_usd=amount(role.check_size_max),
        ebitda_floor_usd=amount(role.ebitda_floor),
        owner_id=org.owner_attio_id,
        status=role.mandate_status,
        contact_ids=(role.key_contact_attio_id,) if role.key_contact_attio_id else (),
        notes=role.notes,
        etag=role.updated_at.isoformat(),
        company_sector=", ".join(org.sector_focus) or None,
    )


def to_seller(
    role: SellerRoleRow, org: Organization, contacts: dict[str, list[Person]]
) -> SellerRole:
    re_engage: date | None = role.re_engage_date
    return SellerRole(
        id=str(role.id),
        name=org.name,
        hq=org.hq_country,
        website=org.domains[0] if org.domains else None,
        sector=", ".join(role.sector or org.sector_focus) or None,
        own_sector=", ".join(role.sector) or None,
        company_sector=", ".join(org.sector_focus) or None,
        geography=org.region or org.hq_country,
        est_revenue_usd=amount(role.est_revenue),
        est_ebitda_usd=amount(role.est_ebitda),
        open_to_selling=open_to_selling(role.appetite_signal),
        appetite_signal=role.appetite_signal,
        re_engage_date=re_engage,
        owner_id=org.owner_attio_id,
        contact_ids=tuple(p.id for p in contacts.get(org.attio_id, [])),
        etag=role.updated_at.isoformat(),
    )


def to_person(row: PersonRow, org_name: str, role: Literal["buyer", "target"]) -> Person:
    return Person(
        id=row.attio_id,
        name=row.name,
        org=org_name,
        role=role,
        title=row.job_title or row.role,
        email=first_email(row.email),
    )
