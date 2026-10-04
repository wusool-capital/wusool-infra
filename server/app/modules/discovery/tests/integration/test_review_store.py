"""`SqlAlchemyReviewStore` against a real Postgres; skipped when none is reachable."""

import uuid
from datetime import date

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import DiscoveryReview
from app.modules.discovery.config import get_settings
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.outcome import UnverifiedSeller
from app.modules.discovery.persistence.review_store import SqlAlchemyReviewStore
from app.modules.utilities.persistence.engine import get_sessionmaker


async def test_add_get_and_pending_round_trip() -> None:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect():
            pass
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")
    finally:
        await engine.dispose()

    sessionmaker = get_sessionmaker(get_settings().database_url)
    store = SqlAlchemyReviewStore(sessionmaker)
    place_id = f"place-{uuid.uuid4()}"
    draft = SellerDraft(
        org_name="Acme Co",
        values={"domains": ["acme.com"], "foundation_date": date(2015, 3, 1), "years_active": 11},
        source_urls=("https://maps.example/acme",),
        source_place_id=place_id,
    )
    unverified = UnverifiedSeller(draft=draft, maps_website=None, provider_websites=(), values=())
    try:
        await store.add(unverified)
        await store.add(unverified)  # an upsert, not a duplicate-key error

        assert await store.pending_place_ids([place_id, "other"]) == {place_id}
        loaded = await store.get_draft(place_id)
        assert loaded is not None
        assert loaded.values == {
            "domains": ["acme.com"],
            "foundation_date": "2015-03-01",
            "years_active": 11,
        }
        assert loaded.source_urls == draft.source_urls
        assert await store.get_draft("missing") is None
    finally:
        async with sessionmaker() as session:
            await session.execute(
                delete(DiscoveryReview).where(DiscoveryReview.place_id == place_id)
            )
            await session.commit()
