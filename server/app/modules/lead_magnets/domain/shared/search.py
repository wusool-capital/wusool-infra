"""One web-search result, flattened.

Whatever the search vendor returns gets reduced to this before it reaches
`application/` — the comparables pipeline only ever needs somewhere to point
the selecting model at, and keeping the vendor's own envelope out of the
seam is what lets the provider be swapped or faked.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
