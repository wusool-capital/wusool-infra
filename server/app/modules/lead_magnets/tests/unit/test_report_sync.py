"""`ReportSync`: what a Sanity publish does to the Webflow Insights card."""

from app.modules.lead_magnets.application.insights_report.sync import ReportSync
from app.modules.lead_magnets.domain.insights_report.report import CmsItem, ReportDocument


def _report(slug: str = "buyouts-in-the-gcc", *, featured: bool = False) -> ReportDocument:
    return ReportDocument(
        slug=slug, title="Buyouts", html="<p>x</p>", excerpt="E", featured=featured
    )


class _FakeSource:
    def __init__(self, *reports: ReportDocument) -> None:
        self._reports = {r.slug: r for r in reports}

    async def get(self, slug: str) -> ReportDocument | None:
        raise AssertionError("the sync must read fresh, never the cached copy")

    async def refresh(self, slug: str) -> ReportDocument | None:
        return self._reports.get(slug)


class _FakeCms:
    def __init__(self, items: dict[str, CmsItem] | None = None, featured: list[str] | None = None):
        self.items = items or {}
        self.featured = featured or []
        self.calls: list[tuple[str, str]] = []

    async def find(self, slug: str) -> CmsItem | None:
        return self.items.get(slug)

    async def create(self, report: ReportDocument) -> None:
        self.calls.append(("create", report.slug))

    async def update(self, item_id: str, report: ReportDocument) -> None:
        self.calls.append(("update", item_id))

    async def unpublish(self, item_id: str) -> None:
        self.calls.append(("unpublish", item_id))

    async def featured_ids(self) -> list[str]:
        return self.featured

    async def unfeature(self, item_id: str) -> None:
        self.calls.append(("unfeature", item_id))


async def test_a_new_report_creates_its_card() -> None:
    cms = _FakeCms()
    await ReportSync(source=_FakeSource(_report()), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug="buyouts-in-the-gcc"
    )
    assert cms.calls == [("create", "buyouts-in-the-gcc")]


async def test_an_existing_gated_card_is_updated() -> None:
    cms = _FakeCms({"buyouts-in-the-gcc": CmsItem(id="item-1", gated=True)})
    await ReportSync(source=_FakeSource(_report()), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug=None
    )
    assert cms.calls == [("update", "item-1")]


async def test_a_hand_written_article_with_the_same_slug_is_never_touched() -> None:
    cms = _FakeCms({"buyouts-in-the-gcc": CmsItem(id="article", gated=False)})
    await ReportSync(source=_FakeSource(_report(featured=True)), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug=None
    )
    assert cms.calls == []


async def test_featuring_a_report_unpins_every_other_card() -> None:
    cms = _FakeCms(
        {"buyouts-in-the-gcc": CmsItem(id="item-1", gated=True)}, featured=["lbo", "item-1"]
    )
    await ReportSync(source=_FakeSource(_report(featured=True)), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug=None
    )
    assert cms.calls == [("unfeature", "lbo"), ("update", "item-1")]


async def test_a_deleted_or_unpublished_report_unpublishes_its_card() -> None:
    cms = _FakeCms({"buyouts-in-the-gcc": CmsItem(id="item-1", gated=True)})
    await ReportSync(source=_FakeSource(), cms=cms).sync(
        slug=None, previous_slug="buyouts-in-the-gcc"
    )
    assert cms.calls == [("unpublish", "item-1")]


async def test_a_renamed_slug_unpublishes_the_old_card_and_creates_the_new_one() -> None:
    cms = _FakeCms({"old-slug": CmsItem(id="item-1", gated=True)})
    await ReportSync(source=_FakeSource(_report("new-slug")), cms=cms).sync(
        slug="new-slug", previous_slug="old-slug"
    )
    assert cms.calls == [("unpublish", "item-1"), ("create", "new-slug")]
