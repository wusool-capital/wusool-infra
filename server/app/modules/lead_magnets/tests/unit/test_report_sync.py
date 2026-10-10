"""`ReportSync`: what a Sanity publish does to the flattened report and the
Webflow Reports card."""

import pytest

from app.modules.lead_magnets.application.insights_report.sync import ReportSync
from app.modules.lead_magnets.domain.insights_report.report import (
    LostPins,
    ReportDocument,
    ReportSource,
    fingerprint,
)
from app.modules.lead_magnets.domain.insights_report.split import split_report


def _report(
    slug: str = "buyouts-in-the-gcc", *, featured: bool = False, banner_pinned: bool = False
) -> ReportDocument:
    return ReportDocument(
        document_id="doc-1",
        slug=slug,
        title="Buyouts",
        html="<p>x</p>",
        excerpt="E",
        featured=featured,
        banner_pinned=banner_pinned,
    )


class _FakeSource:
    """Every report already flattened from its current HTML, unless `stale`."""

    def __init__(self, *reports: ReportDocument, stale: bool = False, free_pages: int = 1) -> None:
        self._reports = {r.slug: r for r in reports}
        self._stale = stale
        self.free_pages = free_pages
        self.superseded = False
        self.saved: list[tuple[str, str, int, str]] = []
        # Per pin, the slugs of the other reports still ticked in Sanity.
        self.ticked: dict[str, list[str]] = {"featured": [], "banner": []}
        self.unpinned: list[tuple[tuple[str, ...], str, str | None]] = []

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
            free_pages=self.free_pages,
        )

    async def save_rendered(
        self, source: ReportSource, *, html: str, preview_end: int, rendered_from: str
    ) -> bool:
        if self.superseded:
            return False
        self.saved.append((source.document_id, html, preview_end, rendered_from))
        return True

    async def unpin_others(self, pins, document_id: str, *, pinned_at: str | None):
        self.unpinned.append((tuple(pins), document_id, pinned_at))
        lost: dict[str, list[str]] = {}
        for pin in pins:
            for slug in self.ticked[pin]:
                lost.setdefault(slug, []).append(pin)
            self.ticked[pin] = []
        return [LostPins(slug=slug, pins=tuple(p)) for slug, p in sorted(lost.items())]


class _FakeRenderer:
    def __init__(self) -> None:
        self.rendered: list[str] = []
        self.free_pages: list[int] = []

    async def render(self, html: str, *, free_pages: int = 1) -> str:
        self.rendered.append(html)
        self.free_pages.append(free_pages)
        return f"<flat>{html}</flat>"

    async def pdf(self, html: str) -> bytes:
        raise AssertionError("the sync never prints")


def _sync(*, source: _FakeSource, cms: "_FakeCms", renderer: _FakeRenderer | None = None):
    return ReportSync(source=source, cms=cms, renderer=renderer or _FakeRenderer())


class _FakeCms:
    def __init__(self, items: dict[str, str] | None = None, fail_update: bool = False):
        self.items = items or {}
        self.fail_update = fail_update
        self.calls: list[tuple[str, str]] = []
        self.written: list[ReportDocument] = []

    async def find(self, slug: str) -> str | None:
        return self.items.get(slug)

    async def create(self, report: ReportDocument) -> str:
        self.calls.append(("create", report.slug))
        self.written.append(report)
        return f"new-{report.slug}"

    async def update(self, item_id: str, report: ReportDocument) -> None:
        if self.fail_update:
            raise RuntimeError("Webflow did not publish")
        self.calls.append(("update", item_id))
        self.written.append(report)

    async def unpublish(self, item_id: str) -> None:
        self.calls.append(("unpublish", item_id))

    async def unpin(self, item_id: str, pins) -> None:
        self.calls.append((f"unpin {' '.join(pins)}", item_id))


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


async def test_a_pinned_report_unpins_the_others_in_sanity_and_webflow() -> None:
    source = _FakeSource(_report("x", featured=True))
    source.ticked["featured"] = ["y"]
    cms = _FakeCms({"x": "item-x", "y": "item-y"})

    await _sync(source=source, cms=cms).sync(slug="x", previous_slug="x")

    assert cms.calls == [("update", "item-x"), ("unpin featured", "item-y")]
    assert [pins for pins, _, _ in source.unpinned] == [("featured",)], "the banner is untouched"


async def test_both_pins_move_together_when_one_report_holds_both() -> None:
    source = _FakeSource(_report("x", featured=True, banner_pinned=True))
    source.ticked = {"featured": ["y"], "banner": ["z"]}
    cms = _FakeCms({"x": "item-x", "y": "item-y", "z": "item-z"})

    await _sync(source=source, cms=cms).sync(slug="x", previous_slug="x")

    assert cms.calls == [
        ("update", "item-x"),
        ("unpin featured", "item-y"),
        ("unpin banner", "item-z"),
    ]


async def test_a_report_losing_both_pins_has_its_card_unpinned_once() -> None:
    source = _FakeSource(_report("x", featured=True, banner_pinned=True))
    source.ticked = {"featured": ["y"], "banner": ["y"]}
    cms = _FakeCms({"x": "item-x", "y": "item-y"})

    await _sync(source=source, cms=cms).sync(slug="x", previous_slug="x")

    assert cms.calls == [("update", "item-x"), ("unpin featured banner", "item-y")]
    assert len(source.unpinned) == 1, "one Sanity transaction for both pins"


async def test_pinning_a_new_report_unpins_the_others_after_its_card_is_live() -> None:
    source = _FakeSource(_report(featured=True))
    source.ticked["featured"] = ["lbo"]
    cms = _FakeCms({"lbo": "item-lbo"})

    await _sync(source=source, cms=cms).sync(slug="buyouts-in-the-gcc", previous_slug=None)

    assert cms.calls == [("create", "buyouts-in-the-gcc"), ("unpin featured", "item-lbo")]


async def test_a_failed_card_write_leaves_every_pin_alone() -> None:
    """Found in prod: unpinning before the card write left /reports empty when the write failed."""
    source = _FakeSource(_report("x", featured=True, banner_pinned=True))
    source.ticked = {"featured": ["y"], "banner": ["y"]}
    cms = _FakeCms({"x": "item-x"}, fail_update=True)
    with pytest.raises(RuntimeError):
        await _sync(source=source, cms=cms).sync(slug="x", previous_slug="x")
    assert source.unpinned == [] and cms.calls == []


async def test_every_sync_writes_the_pins_as_sanity_has_them() -> None:
    """Level-triggered: a lost or superseded earlier sync is repaired by the next one."""
    source = _FakeSource(_report("x"))
    cms = _FakeCms({"x": "item-x"})

    await _sync(source=source, cms=cms).sync(slug="x", previous_slug="x")

    written = cms.written[0]
    assert (written.featured, written.banner_pinned) == (False, False)
    assert source.unpinned == [], "an unpinned report never touches the others"


async def test_the_unpin_passes_the_reports_edit_time_so_the_later_pin_wins() -> None:
    report = ReportDocument(
        document_id="doc-1",
        slug="x",
        title="X",
        html="<p>x</p>",
        featured=True,
        updated_at="2026-10-07T10:00:00Z",
    )
    source = _FakeSource(report)
    await _sync(source=source, cms=_FakeCms({"x": "item-x"})).sync(slug="x", previous_slug="x")
    assert source.unpinned == [(("featured",), "doc-1", "2026-10-07T10:00:00Z")]


async def test_renaming_a_pinned_report_keeps_its_pins() -> None:
    cms = _FakeCms({"old": "item-old"})
    await _sync(
        source=_FakeSource(_report("new", featured=True, banner_pinned=True)), cms=cms
    ).sync(slug="new", previous_slug="old")
    assert cms.calls == [("unpublish", "item-old"), ("create", "new")]
    assert (cms.written[0].featured, cms.written[0].banner_pinned) == (True, True)


async def test_unpublishing_a_pinned_report_touches_no_other_card() -> None:
    """Webflow's featured sort falls back to the newest card; the banner just hides."""
    cms = _FakeCms({"x": "item-x"})
    await _sync(source=_FakeSource(), cms=cms).sync(slug=None, previous_slug="x")
    assert cms.calls == [("unpublish", "item-x")]


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


async def test_changing_only_the_free_pages_flattens_again() -> None:
    source, renderer = _FakeSource(_report(), free_pages=2), _FakeRenderer()

    await _sync(source=source, cms=_FakeCms(), renderer=renderer).sync(
        slug="buyouts-in-the-gcc", previous_slug=None
    )

    assert renderer.free_pages == [2]
    assert source.saved[0][3] == fingerprint("<p>x</p>", 2)


async def test_a_render_superseded_by_a_newer_edit_is_dropped_and_touches_nothing() -> None:
    """Two quick publishes: the older render loses the revision check and must
    not then write the card; the newer edit's own webhook does that."""
    source, cms = _FakeSource(_report(), stale=True), _FakeCms()
    source.superseded = True

    await _sync(source=source, cms=cms).sync(slug="buyouts-in-the-gcc", previous_slug=None)

    assert source.saved == [] and cms.calls == []
