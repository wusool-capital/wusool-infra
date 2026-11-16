from app.modules.interactions.application.ports.review import OpenReview
from app.modules.interactions.application.review_digest import ReviewDigestService
from app.modules.interactions.domain.linking import Ambiguity, RecordDirectory, shared_domain_of


class _Store:
    def __init__(self, *items: OpenReview) -> None:
        self.items = items

    async def save_open(self, cases) -> None:
        raise AssertionError("not used")

    async def list_open(self) -> tuple[OpenReview, ...]:
        return self.items


class _Poster:
    def __init__(self) -> None:
        self.posts: list[str] = []

    async def post(self, text: str) -> None:
        self.posts.append(text)


async def test_nothing_is_posted_when_nothing_is_open() -> None:
    poster = _Poster()

    listed = await ReviewDigestService(_Store(), poster).run()

    assert (listed, poster.posts) == (0, [])


async def test_open_items_are_listed_with_their_kind_value_and_subject() -> None:
    poster = _Poster()
    items = (
        OpenReview(Ambiguity.SHARED_EMAIL, "info@acme.com", "Term sheet", 2),
        OpenReview(Ambiguity.SHARED_DOMAIN, "acme.com", None, 3),
    )

    listed = await ReviewDigestService(_Store(*items), poster).run()

    assert listed == 2
    (text,) = poster.posts
    assert "2 to review" in text
    assert "shared address `info@acme.com` (2 records) — Term sheet" in text
    assert "shared domain `acme.com` (3 records)" in text


async def test_a_long_backlog_is_cut_short_and_says_how_many_more() -> None:
    poster = _Poster()
    items = tuple(OpenReview(Ambiguity.SHARED_EMAIL, f"a{i}@acme.com", None, 2) for i in range(25))

    listed = await ReviewDigestService(_Store(*items), poster).run()

    assert listed == 20
    assert "…and 5 more" in poster.posts[0]


def test_the_shared_domain_is_the_first_one_with_any_match() -> None:
    directory = RecordDirectory({}, {"acme.com": ("o1", "o2"), "co.uk": ("o3",)})

    assert shared_domain_of("sara@mail.acme.com", directory) == ("acme.com", ("o1", "o2"))


def test_no_shared_domain_when_the_nearest_match_is_unique() -> None:
    directory = RecordDirectory({}, {"mail.acme.com": ("o1",), "acme.com": ("o2", "o3")})

    assert shared_domain_of("sara@mail.acme.com", directory) is None
