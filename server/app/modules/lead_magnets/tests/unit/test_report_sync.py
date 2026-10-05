"""`ReportSync`: what a Sanity publish does to the flattened report and the
Webflow Insights card."""

from app.modules.lead_magnets.application.insights_report.sync import ReportSync
from app.modules.lead_magnets.domain.insights_report.report import (
    CmsItem,
    ReportDocument,
    ReportSource,
    fingerprint,
)
from app.modules.lead_magnets.domain.insights_report.split import split_report


def _report(slug: str = "buyouts-in-the-gcc", *, featured: bool = False) -> ReportDocument:
    return ReportDocument(
        slug=slug, title="Buyouts", html="<p>x</p>", excerpt="E", featured=featured
    )


class _FakeSource:
    """Every report already flattened from its current HTML, unless `stale`."""

    def __init__(self, *reports: ReportDocument, stale: bool = False) -> None:
        self._reports = {r.slug: r for r in reports}
        self._stale = stale
        self.superseded = False
        self.saved: list[tuple[str, str, int, str]] = []

    async def get(self, slug: str) -> ReportDocument | None:
        raise AssertionError("the sync must read fresh, never the cached copy")

    async def refresh(self, slug: str) -> ReportDocument | None:
        return self._reports.get(slug)

    async def source(self, slug: str) -> ReportSource | None:
        report = self._reports.get(slug)
        if report is None:
            return None
        rendered_from = None if self._stale else fingerprint(report.html)
        return ReportSource(
            document_id=f"id-{slug}",
            revision="rev-1",
            html=report.html,
            rendered_from=rendered_from,
        )

    async def save_rendered(
        self, source: ReportSource, *, html: str, preview_end: int, rendered_from: str
    ) -> bool:
        if self.superseded:
            return False
        self.saved.append((source.document_id, html, preview_end, rendered_from))
        return True


class _FakeRenderer:
    def __init__(self) -> None:
        self.rendered: list[str] = []

    async def render(self, html: str) -> str:
        self.rendered.append(html)
        return f"<flat>{html}</flat>"


def _sync(*, source: _FakeSource, cms: "_FakeCms", renderer: _FakeRenderer | None = None):
    return ReportSync(source=source, cms=cms, renderer=renderer or _FakeRenderer())


class _FakeCms:
    def __init__(self, items: dict[str, CmsItem] | None = None, featured: list[str] | None = None):
        self.items = items or {}
        self.featured = featured or []
        self.calls: list[tuple[str, str]] = []
        self.pins: list[bool | None] = []

    async def find(self, slug: str) -> CmsItem | None:
        return self.items.get(slug)

    async def create(self, report: ReportDocument, *, featured: bool | None) -> None:
        self.calls.append(("create", report.slug))
        self.pins.append(featured)

    async def update(self, item_id: str, report: ReportDocument, *, featured: bool | None) -> None:
        self.calls.append(("update", item_id))
        self.pins.append(featured)

    async def unpublish(self, item_id: str) -> None:
        self.calls.append(("unpublish", item_id))

    async def featured_ids(self) -> list[str]:
        return self.featured

    async def unfeature(self, item_id: str) -> None:
        self.calls.append(("unfeature", item_id))


async def test_a_new_report_creates_its_card() -> None:
    cms = _FakeCms()
    await _sync(source=_FakeSource(_report()), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug="buyouts-in-the-gcc"
    )
    assert cms.calls == [("create", "buyouts-in-the-gcc")]


async def test_an_existing_gated_card_is_updated() -> None:
    cms = _FakeCms({"buyouts-in-the-gcc": CmsItem(id="item-1", gated=True)})
    await _sync(source=_FakeSource(_report()), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug=None
    )
    assert cms.calls == [("update", "item-1")]


async def test_a_hand_written_article_with_the_same_slug_is_never_touched() -> None:
    cms = _FakeCms({"buyouts-in-the-gcc": CmsItem(id="article", gated=False)})
    await _sync(source=_FakeSource(_report(featured=True)), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug=None, featured_changed=True
    )
    assert cms.calls == []


async def test_ticking_the_pin_unpins_every_other_card() -> None:
    cms = _FakeCms(
        {"buyouts-in-the-gcc": CmsItem(id="item-1", gated=True)}, featured=["lbo", "item-1"]
    )
    await _sync(source=_FakeSource(_report(featured=True)), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug=None, featured_changed=True
    )
    assert cms.calls == [("unfeature", "lbo"), ("update", "item-1")]
    assert cms.pins == [True]


async def test_editing_an_already_pinned_report_does_not_steal_the_pin_back() -> None:
    """Report X was unpinned in Webflow when Y was pinned, but X still says
    "pinned" in Sanity. A typo fix on X must not re-pin it."""
    cms = _FakeCms({"x": CmsItem(id="item-x", gated=True)}, featured=["item-y"])
    await _sync(source=_FakeSource(_report("x", featured=True)), cms=cms).sync(
        slug="x", previous_slug="x", featured_changed=False
    )
    assert cms.calls == [("update", "item-x")]
    assert cms.pins == [None], "the pin is left as Webflow has it"


async def test_unticking_the_pin_unpins_only_that_card() -> None:
    cms = _FakeCms({"x": CmsItem(id="item-x", gated=True)}, featured=["item-x"])
    await _sync(source=_FakeSource(_report("x", featured=False)), cms=cms).sync(
        slug="x", previous_slug="x", featured_changed=True
    )
    assert cms.calls == [("update", "item-x")]
    assert cms.pins == [False]


async def test_a_deleted_or_unpublished_report_unpublishes_its_card() -> None:
    cms = _FakeCms({"buyouts-in-the-gcc": CmsItem(id="item-1", gated=True)})
    await _sync(source=_FakeSource(), cms=cms).sync(slug=None, previous_slug="buyouts-in-the-gcc")
    assert cms.calls == [("unpublish", "item-1")]


async def test_a_renamed_slug_unpublishes_the_old_card_and_creates_the_new_one() -> None:
    cms = _FakeCms({"old-slug": CmsItem(id="item-1", gated=True)})
    await _sync(source=_FakeSource(_report("new-slug")), cms=cms).sync(
        slug="new-slug", previous_slug="old-slug"
    )
    assert cms.calls == [("unpublish", "item-1"), ("create", "new-slug")]


async def test_a_new_html_version_is_flattened_once_and_saved_back() -> None:
    source, renderer = _FakeSource(_report(), stale=True), _FakeRenderer()

    await _sync(source=source, cms=_FakeCms(), renderer=renderer).sync(
        slug="buyouts-in-the-gcc", previous_slug=None
    )

    assert renderer.rendered == ["<p>x</p>"]
    flat = "<flat><p>x</p></flat>"
    preview_end = len(split_report(flat)[0])
    assert source.saved == [("id-buyouts-in-the-gcc", flat, preview_end, fingerprint("<p>x</p>"))]


async def test_an_already_flattened_version_is_not_rendered_again() -> None:
    """A title or pin edit must not spin up Chromium."""
    source, renderer = _FakeSource(_report()), _FakeRenderer()

    await _sync(source=source, cms=_FakeCms(), renderer=renderer).sync(
        slug="buyouts-in-the-gcc", previous_slug=None
    )

    assert renderer.rendered == [] and source.saved == []


async def test_a_render_superseded_by_a_newer_edit_is_dropped_and_touches_nothing() -> None:
    """Two quick publishes: the older render loses the revision check and must
    not then write the card; the newer edit's own webhook does that."""
    source, cms = _FakeSource(_report(), stale=True), _FakeCms()
    source.superseded = True

    await _sync(source=source, cms=cms).sync(slug="buyouts-in-the-gcc", previous_slug=None)

    assert source.saved == [] and cms.calls == []


async def test_without_a_webflow_token_reports_still_render_but_get_no_card() -> None:
    source, renderer = _FakeSource(_report(), stale=True), _FakeRenderer()

    await ReportSync(source=source, cms=None, renderer=renderer).sync(
        slug="buyouts-in-the-gcc", previous_slug="old-slug"
    )

    assert renderer.rendered == ["<p>x</p>"]
    assert len(source.saved) == 1
