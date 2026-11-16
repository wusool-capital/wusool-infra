"""The sent-values store on a real Postgres: seeding, saving, loading and the seed marker."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AttioSentValue
from app.modules.interactions.application.ports.sent_values import SeedRow
from app.modules.interactions.domain.attio_fields import AttioObject
from app.modules.interactions.persistence.sent_values import SqlAlchemySentValues


@pytest.fixture
async def clean(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> AsyncIterator[None]:
    yield
    async with sessionmaker() as session, session.begin():
        await session.execute(
            delete(AttioSentValue).where(
                or_(
                    AttioSentValue.record_attio_id.like(f"{record_prefix}%"),
                    AttioSentValue.record_attio_id == "",
                )
            )
        )


async def test_seed_save_and_load_round_trip_and_the_baseline_survives_a_save(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str, clean: None
) -> None:
    store = SqlAlchemySentValues(sessionmaker)
    rid = f"{record_prefix}o"
    written = await store.seed(
        AttioObject.ORGANIZATIONS,
        [
            SeedRow(rid, "connection_strength", "Weak", "Good"),
            SeedRow(rid, "first_interaction_at", None, "2024-01-01T00:00:00.000+00:00"),
        ],
    )

    await store.save(AttioObject.ORGANIZATIONS, rid, {"connection_strength": "Strong"})
    loaded = (await store.load(AttioObject.ORGANIZATIONS))[rid]

    assert written == 2
    assert loaded.sent == {"connection_strength": "Strong", "first_interaction_at": None}
    assert loaded.baseline == {
        "connection_strength": "Good",
        "first_interaction_at": "2024-01-01T00:00:00.000+00:00",
    }


async def test_seeding_again_never_overwrites_what_is_stored(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str, clean: None
) -> None:
    store = SqlAlchemySentValues(sessionmaker)
    rid = f"{record_prefix}p"
    await store.seed(AttioObject.PERSON, [SeedRow(rid, "connection_strength", "Weak", None)])

    again = await store.seed(
        AttioObject.PERSON, [SeedRow(rid, "connection_strength", "Strong", None)]
    )

    assert again == 0
    assert (await store.load(AttioObject.PERSON))[rid].sent == {"connection_strength": "Weak"}


async def test_objects_are_kept_apart_and_a_record_that_was_never_seeded_is_absent(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str, clean: None
) -> None:
    store = SqlAlchemySentValues(sessionmaker)
    rid = f"{record_prefix}x"
    await store.save(AttioObject.ORGANIZATIONS, rid, {"connection_strength": "Weak"})

    assert rid in await store.load(AttioObject.ORGANIZATIONS)
    assert rid not in await store.load(AttioObject.PERSON)


async def test_the_seed_marker_is_per_object_and_never_listed_as_a_record(
    sessionmaker: async_sessionmaker[AsyncSession], clean: None
) -> None:
    store = SqlAlchemySentValues(sessionmaker)
    assert not await store.is_seeded(AttioObject.ORGANIZATIONS)

    await store.mark_seeded(AttioObject.ORGANIZATIONS)
    await store.mark_seeded(AttioObject.ORGANIZATIONS)

    assert await store.is_seeded(AttioObject.ORGANIZATIONS)
    assert not await store.is_seeded(AttioObject.PERSON)
    assert "" not in await store.load(AttioObject.ORGANIZATIONS)
