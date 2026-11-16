from collections.abc import Sequence

from app.modules.interactions.application.ports.review import OpenReview, ReviewCase
from app.modules.interactions.application.review_digest import ReviewDigestService
from app.modules.interactions.domain.linking import Ambiguity, RecordDirectory, shared_domain_of


class _Store:
    def __init__(self, *items: OpenReview) -> None:
        self.items = items
        self.marked: list[OpenReview] = []

    async def sync_open(self, cases: Sequence[ReviewCase]) -> None:
        raise AssertionError("not used")

    async def list_open(self) -> tuple[OpenReview, ...]:
        return self.items

    async def mark_notified(self, items: Sequence[OpenReview]) -> None:
        self.marked.extend(items)


class _Poster:
    def __init__(self, *, failing: bool = False) -> None:
        self.posts: list[str] = []
        self.failing = failing

    async def post(self, text: str) -> None:
        if self.failing:
            raise RuntimeError("slack is down")
        self.posts.append(text)


def _item(
    value: str, *, notified: bool = False, kind: Ambiguity = Ambiguity.SHARED_EMAIL
) -> OpenReview:
    return OpenReview(kind, value, None, 2, notified)


async def test_nothing_is_posted_when_nothing_is_new() -> None:
    poster, store = _Poster(), _Store(_item("a@acme.com", notified=True))

    listed = await ReviewDigestService(store, poster).run()

    assert (listed, poster.posts, store.marked) == (0, [], [])


async def test_new_items_are_listed_with_their_kind_value_and_subject_then_marked() -> None:
    poster = _Poster()
    items = (
        OpenReview(Ambiguity.SHARED_EMAIL, "info@acme.com", "Term sheet", 2),
        OpenReview(Ambiguity.SHARED_DOMAIN, "acme.com", None, 3),
        _item("old@acme.com", notified=True),
    )
    store = _Store(*items)

    listed = await ReviewDigestService(store, poster).run()

    assert listed == 2
    (text,) = poster.posts
    assert "2 new to review" in text and "3 open in total" in text
    assert "shared address `info@acme.com` (2 records) — Term sheet" in text
    assert "shared domain `acme.com` (3 records)" in text
    assert "old@acme.com" not in text
    assert store.marked == list(items[:2])


async def test_a_failed_post_marks_nothing_so_it_is_tried_again() -> None:
    store = _Store(_item("a@acme.com"))

    try:
        await ReviewDigestService(store, _Poster(failing=True)).run()
    except RuntimeError:
        pass

    assert store.marked == []


async def test_a_long_backlog_lists_twenty_and_marks_only_those() -> None:
    poster = _Poster()
    store = _Store(*(_item(f"a{i}@acme.com") for i in range(25)))

    listed = await ReviewDigestService(store, poster).run()

    assert (listed, len(store.marked)) == (20, 20)
    assert "…and 5 more, in the next post" in poster.posts[0]


def test_the_shared_domain_is_the_first_one_with_any_match() -> None:
    directory = RecordDirectory({}, {"acme.com": ("o1", "o2"), "co.uk": ("o3",)})

    assert shared_domain_of("sara@mail.acme.com", directory) == ("acme.com", ("o1", "o2"))


def test_no_shared_domain_when_the_nearest_match_is_unique() -> None:
    directory = RecordDirectory({}, {"mail.acme.com": ("o1",), "acme.com": ("o2", "o3")})

    assert shared_domain_of("sara@mail.acme.com", directory) is None
