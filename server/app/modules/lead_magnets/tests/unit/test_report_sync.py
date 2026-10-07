"""`ReportSync`: what a Sanity publish does to the flattened report and the
Webflow Reports card."""

import pytest

from app.modules.lead_magnets.application.insights_report.sync import ReportSync
from app.modules.lead_magnets.domain.insights_report.report import (
    ReportDocument,
    ReportSource,
    fingerprint,
)
from app.modules.lead_magnets.domain.insights_report.split import split_report


def _report(
    slug: str = "buyouts-in-the-gcc", *, featured: bool = False, banner_pinned: bool = False
) -> ReportDocument:
    return ReportDocument(
        slug=slug,
        title="Buyouts",
        html="<p>x</p>",
        excerpt="E",
        featured=featured,
        banner_pinned=banner_pinned,
    )


class _FakeSource:
    """Every report already flattened from its current HTML, unless `stale`."""

    def __init__(self, *reports: ReportDocument, stale: bool = False) -> None:
        self._reports = {r.slug: r for r in reports}
        self._stale = stale
        self.superseded = False
        self.saved: list[tuple[str, str, int, str]] = []
        # Slugs of the other reports still ticked for the banner in Sanity.
        self.banner: list[str] = []
        self.unpinned: list[tuple[str, str | None]] = []

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

    async def unpin_banner_except(self, slug: str, *, pinned_at: str | None) -> list[str]:
        self.unpinned.append((slug, pinned_at))
        others, self.banner = [s for s in self.banner if s != slug], []
        return others


class _FakeRenderer:
    def __init__(self) -> None:
        self.rendered: list[str] = []

    async def render(self, html: str) -> str:
        self.rendered.append(html)
        return f"<flat>{html}</flat>"

    async def pdf(self, html: str) -> bytes:
        raise AssertionError("the sync never prints")


def _sync(*, source: _FakeSource, cms: "_FakeCms", renderer: _FakeRenderer | None = None):
    return ReportSync(source=source, cms=cms, renderer=renderer or _FakeRenderer())


class _FakeCms:
    def __init__(
        self,
        items: dict[str, str] | None = None,
        featured: list[str] | None = None,
        newest_first: list[str] | None = None,
        fail_update: bool = False,
    ):
        self.items = items or {}
        self.featured = featured or []
        self.newest_first = newest_first or []
        self.fail_update = fail_update
        self.calls: list[tuple[str, str]] = []
        self.pins: list[bool | None] = []
        self.banner_pins: list[bool | None] = []

    async def find(self, slug: str) -> str | None:
        return self.items.get(slug)

    async def create(
        self, report: ReportDocument, *, featured: bool | None, banner_pinned: bool | None
    ) -> str:
        self.calls.append(("create", report.slug))
        self.pins.append(featured)
        self.banner_pins.append(banner_pinned)
        return f"new-{report.slug}"

    async def update(
        self,
        item_id: str,
        report: ReportDocument,
        *,
        featured: bool | None,
        banner_pinned: bool | None,
    ) -> None:
        if self.fail_update:
            raise RuntimeError("Webflow did not publish")
        self.calls.append(("update", item_id))
        self.pins.append(featured)
        self.banner_pins.append(banner_pinned)

    async def unpublish(self, item_id: str) -> None:
        self.calls.append(("unpublish", item_id))

    async def featured_ids(self) -> list[str]:
        return self.featured

    async def newest_id(self, *, excluding: str | None = None) -> str | None:
        return next((i for i in self.newest_first if i != excluding), None)

    async def feature(self, item_id: str) -> None:
        self.calls.append(("feature", item_id))

    async def unfeature(self, item_id: str) -> None:
        self.calls.append(("unfeature", item_id))

    async def unpin_banner(self, item_id: str) -> None:
        self.calls.append(("unpin_banner", item_id))


async def test_a_new_report_creates_its_card() -> None:
    cms = _FakeCms()
    await _sync(source=_FakeSource(_report()), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug="buyouts-in-the-gcc"
    )
    assert cms.calls == [("create", "buyouts-in-the-gcc")]


async def test_an_existing_card_is_updated() -> None:
    cms = _FakeCms({"buyouts-in-the-gcc": "item-1"})
    await _sync(source=_FakeSource(_report()), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug=None
    )
    assert cms.calls == [("update", "item-1")]


async def test_ticking_the_pin_unpins_every_other_card() -> None:
    cms = _FakeCms({"buyouts-in-the-gcc": "item-1"}, featured=["lbo", "item-1"])
    await _sync(source=_FakeSource(_report(featured=True)), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug=None, featured_changed=True
    )
    assert cms.calls == [("update", "item-1"), ("unfeature", "lbo")]
    assert cms.pins == [True]


async def test_pinning_a_new_report_never_unpins_the_card_it_just_created() -> None:
    cms = _FakeCms(featured=["lbo", "new-buyouts-in-the-gcc"])
    await _sync(source=_FakeSource(_report(featured=True)), cms=cms).sync(
        slug="buyouts-in-the-gcc", previous_slug=None, featured_changed=True
    )
    assert cms.calls == [("create", "buyouts-in-the-gcc"), ("unfeature", "lbo")]


async def test_a_failed_card_write_leaves_the_current_pin_alone() -> None:
    """Found in prod: the old order unpinned LBO, then the card write failed,
    and /insights showed "No items found"."""
    cms = _FakeCms({"buyouts-in-the-gcc": "item-1"}, featured=["lbo"], fail_update=True)
    with pytest.raises(RuntimeError):
        await _sync(source=_FakeSource(_report(featured=True)), cms=cms).sync(
            slug="buyouts-in-the-gcc", previous_slug=None, featured_changed=True
        )
    assert cms.calls == []


async def test_unpublishing_the_pinned_report_pins_the_newest_live_card() -> None:
    cms = _FakeCms({"x": "item-x"}, newest_first=["lbo", "exit"])
    await _sync(source=_FakeSource(), cms=cms).sync(slug=None, previous_slug="x")
    assert cms.calls == [("unpublish", "item-x"), ("feature", "lbo")]


async def test_unticking_the_newest_report_pins_the_next_newest_not_itself() -> None:
    cms = _FakeCms(
        {"x": "item-x"},
        featured=["item-x"],
        newest_first=["item-x", "lbo"],
    )
    await _sync(source=_FakeSource(_report("x", featured=False)), cms=cms).sync(
        slug="x", previous_slug="x", featured_changed=True
    )
    assert cms.calls == [("update", "item-x"), ("feature", "lbo")]


async def test_nothing_is_repinned_while_another_card_holds_the_pin() -> None:
    cms = _FakeCms({"x": "item-x"}, featured=["lbo"], newest_first=["x"])
    await _sync(source=_FakeSource(_report("x")), cms=cms).sync(slug="x", previous_slug="x")
    assert cms.calls == [("update", "item-x")]


async def test_editing_an_already_pinned_report_does_not_steal_the_pin_back() -> None:
    """Report X was unpinned in Webflow when Y was pinned, but X still says
    "pinned" in Sanity. A typo fix on X must not re-pin it."""
    cms = _FakeCms({"x": "item-x"}, featured=["item-y"])
    await _sync(source=_FakeSource(_report("x", featured=True)), cms=cms).sync(
        slug="x", previous_slug="x", featured_changed=False
    )
    assert cms.calls == [("update", "item-x")]
    assert cms.pins == [None], "the pin is left as Webflow has it"


async def test_unticking_the_pin_unpins_only_that_card() -> None:
    cms = _FakeCms({"x": "item-x"}, featured=["item-x"])
    await _sync(source=_FakeSource(_report("x", featured=False)), cms=cms).sync(
        slug="x", previous_slug="x", featured_changed=True
    )
    assert cms.calls == [("update", "item-x")]
    assert cms.pins == [False]


async def test_a_banner_pinned_report_unpins_the_others_in_sanity_and_webflow() -> None:
    source = _FakeSource(_report("x", banner_pinned=True))
    source.banner = ["y"]
    cms = _FakeCms({"x": "item-x", "y": "item-y"}, featured=["lbo"])

    await _sync(source=source, cms=cms).sync(slug="x", previous_slug="x")

    assert cms.calls == [("update", "item-x"), ("unpin_banner", "item-y")]
    assert cms.banner_pins == [True]
    assert cms.pins == [None], "the /reports pin is untouched"


async def test_every_sync_writes_the_banner_pin_as_sanity_has_it() -> None:
    """Level-triggered: a lost or superseded earlier sync is repaired by the next one."""
    cms = _FakeCms({"x": "item-x"}, featured=["lbo"])
    source = _FakeSource(_report("x"))

    await _sync(source=source, cms=cms).sync(slug="x", previous_slug="x")

    assert cms.banner_pins == [False]
    assert source.unpinned == [], "an unpinned report never touches the others"


async def test_renaming_the_banner_report_keeps_it_in_the_banner() -> None:
    cms = _FakeCms({"old": "item-old"}, featured=["lbo"])
    await _sync(source=_FakeSource(_report("new", banner_pinned=True)), cms=cms).sync(
        slug="new", previous_slug="old"
    )
    assert cms.calls == [("unpublish", "item-old"), ("create", "new")]
    assert cms.banner_pins == [True]


async def test_a_failed_card_write_leaves_the_banner_alone() -> None:
    source = _FakeSource(_report("x", banner_pinned=True))
    source.banner = ["y"]
    cms = _FakeCms({"x": "item-x"}, featured=["lbo"], fail_update=True)
    with pytest.raises(RuntimeError):
        await _sync(source=source, cms=cms).sync(slug="x", previous_slug="x")
    assert source.unpinned == [] and cms.calls == []


async def test_a_deleted_or_unpublished_report_unpublishes_its_card() -> None:
    cms = _FakeCms({"buyouts-in-the-gcc": "item-1"})
    await _sync(source=_FakeSource(), cms=cms).sync(slug=None, previous_slug="buyouts-in-the-gcc")
    assert cms.calls == [("unpublish", "item-1")]


async def test_a_renamed_slug_unpublishes_the_old_card_and_creates_the_new_one() -> None:
    cms = _FakeCms({"old-slug": "item-1"})
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
