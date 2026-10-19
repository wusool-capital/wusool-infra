"""Apify implementation of `LinkedInClient` — profile and post scrapes via
HarvestAPI, mapped into the domain's `LinkedInProfile`/`LinkedInPost`.
"""

from datetime import datetime

from app.modules.enrichment.application.ports.linkedin import PostedLimit
from app.modules.enrichment.domain.linkedin import LinkedInPost, LinkedInProfile
from app.modules.enrichment.providers.apify.client import ApifyClient
from app.modules.enrichment.providers.apify.schemas import (
    POSTS_ACTOR,
    PROFILE_ACTOR,
    ApifyPostItem,
    ApifyProfileItem,
    ProfilePostsInput,
    ProfileScraperInput,
)

# Both calls run concurrently inside the use case's own 60s cap.
_RUN_TIMEOUT_S = 40
_PRESENT = "present"


def _map_profile(item: ApifyProfileItem) -> LinkedInProfile | None:
    url = item.linkedinUrl or (
        f"https://www.linkedin.com/in/{item.publicIdentifier}" if item.publicIdentifier else None
    )
    if url is None:
        return None
    current = next((p for p in item.currentPosition if p.companyName), None)
    open_roles = [
        e for e in item.experience if e.endDate and (e.endDate.text or "").casefold() == _PRESENT
    ]
    title = current.position if current else None
    company = current.companyName if current else None
    if open_roles:
        # `currentPosition` omits the title in the actor's sample output, so
        # fall back to the matching open-ended experience entry.
        match = next((e for e in open_roles if company and e.companyName == company), open_roles[0])
        title = title or match.position
        company = company or match.companyName
    return LinkedInProfile(
        url=url,
        headline=item.headline,
        location=item.location.linkedinText if item.location else None,
        current_title=title,
        current_company=company,
    )


def _parse_posted_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _strip_query(url: str | None) -> str | None:
    """The actor appends tracking params (`?miniProfileUrn=…`) to profile URLs."""
    return url.split("?", 1)[0] if url else None


def _map_post(item: ApifyPostItem) -> LinkedInPost | None:
    if not item.id or not item.linkedinUrl:
        return None
    return LinkedInPost(
        external_id=item.id,
        url=item.linkedinUrl,
        text=item.content or "",
        author_name=item.author.name if item.author else None,
        author_url=_strip_query(item.author.linkedinUrl) if item.author else None,
        posted_at=_parse_posted_at(item.postedAt.date if item.postedAt else None),
    )


class ApifyLinkedInClient:
    def __init__(self, token: str) -> None:
        self._client = ApifyClient(token)

    async def profiles(self, urls: tuple[str, ...]) -> tuple[LinkedInProfile, ...]:
        if not urls:
            return ()
        items = await self._client.run(
            actor=PROFILE_ACTOR,
            actor_input=ProfileScraperInput(queries=list(urls)),
            item_type=ApifyProfileItem,
            run_timeout_s=_RUN_TIMEOUT_S,
        )
        return tuple(p for p in (_map_profile(i) for i in items) if p is not None)

    async def posts(
        self, urls: tuple[str, ...], *, max_posts: int, posted_limit: PostedLimit
    ) -> tuple[LinkedInPost, ...]:
        if not urls:
            return ()
        items = await self._client.run(
            actor=POSTS_ACTOR,
            actor_input=ProfilePostsInput(
                targetUrls=list(urls), maxPosts=max_posts, postedLimit=posted_limit
            ),
            item_type=ApifyPostItem,
            run_timeout_s=_RUN_TIMEOUT_S,
        )
        return tuple(p for p in (_map_post(i) for i in items) if p is not None)
