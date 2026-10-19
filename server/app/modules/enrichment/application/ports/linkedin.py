"""The provider-agnostic seam `LinkedInMixin` depends on for scraping
LinkedIn profiles and posts. Both calls take a batch so a role costs one
vendor run each, not one per contact. Fails soft: an empty result on any
provider error.
"""

from typing import Literal, Protocol

from app.modules.enrichment.domain.linkedin import LinkedInPost, LinkedInProfile

PostedLimit = Literal["24h", "week", "month"]


class LinkedInClient(Protocol):
    async def profiles(self, urls: tuple[str, ...]) -> tuple[LinkedInProfile, ...]: ...

    async def posts(
        self, urls: tuple[str, ...], *, max_posts: int, posted_limit: PostedLimit
    ) -> tuple[LinkedInPost, ...]: ...
