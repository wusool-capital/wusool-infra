"""Fake `LinkedInClient` for tests — no network calls."""

import asyncio

from app.modules.enrichment.application.ports.linkedin import LinkedInClient, PostedLimit
from app.modules.enrichment.domain.linkedin import LinkedInPost, LinkedInProfile


class FakeLinkedInClient(LinkedInClient):
    def __init__(
        self,
        profiles: tuple[LinkedInProfile, ...] = (),
        posts: tuple[LinkedInPost, ...] = (),
        *,
        delay_s: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        self._profiles = profiles
        self._posts = posts
        self._delay_s = delay_s
        self._error = error
        self.profile_calls: list[tuple[str, ...]] = []
        self.post_calls: list[tuple[tuple[str, ...], int, PostedLimit]] = []

    async def profiles(self, urls: tuple[str, ...]) -> tuple[LinkedInProfile, ...]:
        self.profile_calls.append(urls)
        await asyncio.sleep(self._delay_s)
        if self._error:
            raise self._error
        return self._profiles

    async def posts(
        self, urls: tuple[str, ...], *, max_posts: int, posted_limit: PostedLimit
    ) -> tuple[LinkedInPost, ...]:
        self.post_calls.append((urls, max_posts, posted_limit))
        await asyncio.sleep(self._delay_s)
        return self._posts
