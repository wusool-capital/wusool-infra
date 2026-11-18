"""Every column of the catalog filters with every operator it allows, as SQL on a real
Postgres; and the NULL, string-amount and escaping rules hold."""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Organization, SellerRole
from app.modules.record_filters import (
    ConditionValue,
    FieldCondition,
    FieldShape,
    FilterOp,
    RecordKind,
    build_catalog,
    condition_sql,
)

_VERTICAL = f"Test vertical {uuid.uuid4()}"
_SAMPLE: dict[FieldShape, ConditionValue] = {
    "text": "x",
    "array": "x",
    "joined_text": "x",
    "money": 1.0,
    "number": 1.0,
    "date": date(2026, 1, 1),
    "datetime": datetime(2026, 1, 1, tzinfo=UTC),
    "bool": True,
}
_ROLE_MODELS: dict[RecordKind, type[BuyerRole] | type[SellerRole]] = {
    "buyer": BuyerRole,
    "seller": SellerRole,
}


def _value(shape: FieldShape, op: FilterOp) -> ConditionValue:
    if op in ("is_set", "is_not_set"):
        return None
    if op == "in":
        return ("x",)
    return _SAMPLE[shape]


def _usd(amount: float | str) -> dict[str, float | str]:
    return {"amount": amount, "currency": "USD"}


_CASES = [
    (kind, field.key, op)
    for kind in ("buyer", "seller")
    for field in build_catalog(kind, []).fields
    for op in field.ops
]


async def _ids(
    session: AsyncSession, kind: RecordKind, *conditions: FieldCondition
) -> set[uuid.UUID]:
    model = _ROLE_MODELS[kind]
    stmt = (
        select(model.id)
        .join(Organization, model.org_attio_id == Organization.attio_id)
        .where(and_(*(condition_sql(kind, c) for c in conditions)))
    )
    return set((await session.execute(stmt)).scalars().all())


@pytest.mark.parametrize(("kind", "key", "op"), _CASES)
async def test_every_column_runs_with_every_op_it_allows(
    db_session: AsyncSession, kind: RecordKind, key: str, op: FilterOp
) -> None:
    field = build_catalog(kind, []).get(key)
    assert field is not None
    condition = FieldCondition(field.target, field.column, field.shape, op, _value(field.shape, op))

    await _ids(db_session, kind, condition)


async def _buyer(session: AsyncSession, org: Organization, **fields) -> BuyerRole:
    role = BuyerRole(org_attio_id=org.attio_id, target_vertical=_VERTICAL, is_active=True)
    for name, value in fields.items():
        setattr(role, name, value)
    session.add(role)
    await session.flush()
    return role


async def _buyers(session: AsyncSession, *conditions: FieldCondition) -> set[uuid.UUID]:
    vertical = FieldCondition("role", "target_vertical", "text", "eq", _VERTICAL)
    return await _ids(session, "buyer", vertical, *conditions)


async def test_money_ranges_skip_unknowns_and_read_numeric_strings(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    big = await _buyer(db_session, throwaway_org, ebitda_ceiling=_usd(5e6))
    legacy = await _buyer(db_session, throwaway_org, ebitda_ceiling=_usd("3000000"))
    junk = await _buyer(db_session, throwaway_org, ebitda_ceiling=_usd("lots"))
    unset = await _buyer(db_session, throwaway_org)

    def cond(op: FilterOp, value: ConditionValue = None) -> FieldCondition:
        return FieldCondition("role", "ebitda_ceiling", "money", op, value)

    assert await _buyers(db_session, cond("gte", 4e6)) == {big.id}
    assert await _buyers(db_session, cond("gte", 2e6)) == {big.id, legacy.id}
    assert await _buyers(db_session, cond("lte", 4e6)) == {legacy.id}
    assert await _buyers(db_session, cond("is_set")) == {big.id, legacy.id}
    assert await _buyers(db_session, cond("is_not_set")) == {junk.id, unset.id}


async def test_text_contains_ignores_case_and_escapes_wildcards(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    liked = await _buyer(db_session, throwaway_org, notes="Likes Fintech deals")
    await _buyer(db_session, throwaway_org, notes="")
    await _buyer(db_session, throwaway_org)

    def cond(op: FilterOp, value: ConditionValue = None) -> FieldCondition:
        return FieldCondition("role", "notes", "text", op, value)

    assert await _buyers(db_session, cond("contains", "fintech")) == {liked.id}
    assert await _buyers(db_session, cond("contains", "%")) == set()
    assert await _buyers(db_session, cond("is_set")) == {liked.id}


async def test_company_columns_filter_buyers_including_a_joined_text(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    throwaway_org.region = "GCC,MENA"
    throwaway_org.sector_focus = ["Fintech", "AI / ML"]
    role = await _buyer(db_session, throwaway_org)
    await db_session.flush()

    def cond(column: str, shape: FieldShape, op: FilterOp, value: ConditionValue) -> FieldCondition:
        return FieldCondition("org", column, shape, op, value)

    assert await _buyers(db_session, cond("region", "joined_text", "in", ("GCC",))) == {role.id}
    assert await _buyers(db_session, cond("region", "joined_text", "in", ("Levant",))) == set()
    assert await _buyers(db_session, cond("region", "joined_text", "eq", "MENA")) == {role.id}
    assert await _buyers(db_session, cond("region", "joined_text", "eq", "GC")) == set()
    assert await _buyers(db_session, cond("sector_focus", "array", "eq", "AI / ML")) == {role.id}
    assert await _buyers(db_session, cond("sector_focus", "array", "in", ("Mining",))) == set()

    hq_set = cond("hq_country", "joined_text", "is_set", None)
    hq_unset = cond("hq_country", "joined_text", "is_not_set", None)
    assert await _buyers(db_session, hq_set) == {role.id}  # the fixture sets "AE"
    assert await _buyers(db_session, hq_unset) == set()
    throwaway_org.hq_country = ""  # empty text counts as unset
    await db_session.flush()
    assert await _buyers(db_session, hq_unset) == {role.id}


async def test_timestamps_filter_by_a_moment_and_by_whether_they_are_set(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _buyer(db_session, throwaway_org)
    throwaway_org.last_interaction_at = datetime(2026, 6, 1, tzinfo=UTC)
    await db_session.flush()

    def cond(op: FilterOp, value: ConditionValue = None) -> FieldCondition:
        return FieldCondition("org", "last_interaction_at", "datetime", op, value)

    after = datetime(2026, 1, 1, tzinfo=UTC)
    later = datetime(2026, 12, 1, tzinfo=UTC)
    assert await _buyers(db_session, cond("gte", after)) == {role.id}
    assert await _buyers(db_session, cond("gte", later)) == set()
    assert await _buyers(db_session, cond("lte", later)) == {role.id}
    assert await _buyers(db_session, cond("is_not_set")) == set()


async def test_seller_ranges_booleans_computed_columns_and_every_condition_must_match(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    sector = f"Test sector {uuid.uuid4()}"
    throwaway_org.sector_focus = [sector]
    seller = SellerRole(
        org_attio_id=throwaway_org.attio_id,
        is_active=True,
        est_ebitda=_usd(2e6),
        years_active=12,
        benchmark_score=71.5,
        ebitda_deducts_salary=True,
        re_engage_date=date(2026, 12, 1),
    )
    db_session.add(seller)
    await db_session.flush()

    async def found(*conditions: FieldCondition) -> set[uuid.UUID]:
        in_sector = FieldCondition("org", "sector_focus", "array", "eq", sector)
        return await _ids(db_session, "seller", in_sector, *conditions)

    ebitda = FieldCondition("role", "est_ebitda", "money", "gte", 1e6)
    years = FieldCondition("role", "years_active", "number", "lte", 10.0)
    score = FieldCondition("role", "benchmark_score", "number", "gte", 70.0)
    flag = FieldCondition("role", "ebitda_deducts_salary", "bool", "eq", True)
    due = FieldCondition("role", "re_engage_date", "date", "lte", date(2026, 12, 31))

    assert await found(ebitda, score, flag, due) == {seller.id}
    assert await found(ebitda, years) == set()
