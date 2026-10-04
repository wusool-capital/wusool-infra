"""Implements `ReviewStore` on `discovery_reviews` (`app/models/discovery_review.py`)."""

from datetime import date

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import DiscoveryReview
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.outcome import UnverifiedSeller


class _StoredDraft(BaseModel):
    """The JSONB `draft` column. Dates come back as ISO strings, which
    `ddl_commands`' prefill shaping turns back into dates."""

    org_name: str
    values: dict[str, str | float | bool | int | date | list[str]]
    source_urls: list[str]
    source_place_id: str | None

    @classmethod
    def from_draft(cls, draft: SellerDraft) -> "_StoredDraft":
        return cls(
            org_name=draft.org_name,
            values=draft.values,
            source_urls=list(draft.source_urls),
            source_place_id=draft.source_place_id,
        )

    def to_draft(self) -> SellerDraft:
        return SellerDraft(
            org_name=self.org_name,
            values=dict(self.values),
            source_urls=tuple(self.source_urls),
            source_place_id=self.source_place_id,
        )


class SqlAlchemyReviewStore:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def pending_place_ids(self, place_ids: list[str]) -> set[str]:
        if not place_ids:
            return set()
        stmt = select(DiscoveryReview.place_id).where(DiscoveryReview.place_id.in_(place_ids))
        async with self._sessionmaker() as session:
            return set((await session.execute(stmt)).scalars())

    async def add(self, unverified: UnverifiedSeller) -> None:
        draft = unverified.draft
        assert draft.source_place_id is not None  # caller only stores keyed leads
        payload = _StoredDraft.from_draft(draft).model_dump(mode="json")
        stmt = insert(DiscoveryReview).values(
            place_id=draft.source_place_id, org_name=draft.org_name, draft=payload
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[DiscoveryReview.place_id],
            set_={"org_name": stmt.excluded.org_name, "draft": stmt.excluded.draft},
        )
        async with self._sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_draft(self, place_id: str) -> SellerDraft | None:
        async with self._sessionmaker() as session:
            row = await session.get(DiscoveryReview, place_id)
        if row is None:
            return None
        return _StoredDraft.model_validate(row.draft).to_draft()
