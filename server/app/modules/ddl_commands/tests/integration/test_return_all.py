"""`return_all` reads every catalog column of real rows and every value serializes."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Organization, SellerRole
from app.modules.ddl_commands.api import flat_records
from app.modules.ddl_commands.api.bulk_store import UploadKind
from app.modules.ddl_commands.api.filter_catalog import filter_catalog


async def _role(
    session: AsyncSession, kind: UploadKind, org: Organization
) -> BuyerRole | SellerRole:
    role: BuyerRole | SellerRole
    if kind == "buyer":
        role = BuyerRole(
            org_attio_id=org.attio_id,
            is_active=True,
            ebitda_ceiling={"amount": "3000000", "currency": "USD"},  # a legacy string amount
            target_country=["Oman"],
            last_mandate_briefing_date=date(2026, 1, 2),
        )
    else:
        role = SellerRole(
            org_attio_id=org.attio_id,
            is_active=True,
            est_ebitda={"amount": 2e6, "currency": "USD"},
            benchmark_score=Decimal("71.5"),
            years_active=12,
            re_engage_date=date(2026, 12, 1),
        )
    org.last_interaction_at = datetime(2026, 6, 1, tzinfo=UTC)
    session.add(role)
    await session.flush()
    await session.refresh(role)
    await session.refresh(org)
    return role


@pytest.mark.parametrize("kind", ["buyer", "seller"])
async def test_every_column_of_a_real_row_comes_back_and_serializes(
    db_session: AsyncSession, throwaway_org: Organization, kind: UploadKind
) -> None:
    role = await _role(db_session, kind, throwaway_org)
    role.organization = throwaway_org

    selected = flat_records._selected(kind, None, default="all")
    detail = flat_records._detail(role, selected)

    assert set(detail.fields) == {f.key for f in filter_catalog(kind).fields}
    assert detail.fields["last_interaction_at"] == "2026-06-01T00:00:00+00:00"
    assert detail.fields["created_at"] is not None  # a server default, read back
    flat_records.RecordDetails(records=(detail,), not_found=(uuid.uuid4(),)).model_dump_json()
    if kind == "buyer":
        assert detail.fields["ebitda_ceiling"] == 3e6
        assert detail.fields["target_country"] == ["Oman"]
    else:
        assert detail.fields["benchmark_score"] == 71.5
        assert detail.fields["re_engage_date"] == "2026-12-01"
