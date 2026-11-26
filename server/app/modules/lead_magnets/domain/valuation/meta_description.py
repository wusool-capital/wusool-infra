"""Reads a page's own description from its HTML, so `/enrich` can skip the
scrape-and-model path when the company already says what it does."""

from html.parser import HTMLParser

MIN_DESCRIPTION_CHARS = 50
# The request schemas cap `description` at 4000, so a longer value would 422 the next call.
MAX_DESCRIPTION_CHARS = 4000


class _Head(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: str | None = None
        self.og: str | None = None
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            content = " ".join(a.get("content", "").split())
            if a.get("name", "").lower() == "description" and not self.meta:
                self.meta = content
            elif a.get("property", "").lower() == "og:description" and not self.og:
                self.og = content

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def usable_description(html: str) -> str | None:
    """`<meta name="description">`, else `og:description`, when it is long
    enough to be a real description and not just the page title."""
    head = _Head()
    head.feed(html)
    title = " ".join(head.title.split()).casefold()
    for candidate in (head.meta, head.og):
        if candidate and len(candidate) >= MIN_DESCRIPTION_CHARS and candidate.casefold() != title:
            return candidate[:MAX_DESCRIPTION_CHARS]
    return None
