"""Records what a Slack handler hands to `propose_and_post`, without running
the real background task or any research."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from types import ModuleType

import pytest

from app.modules.enrichment.domain.targets import EnrichmentTarget


@dataclass(frozen=True)
class EnrichmentCall:
    role_id: str
    channel_id: str
    requested_by: str | None


def record_enrichment_calls(
    monkeypatch: pytest.MonkeyPatch, handler_module: ModuleType
) -> list[EnrichmentCall]:
    """Patches the handler module's `propose_and_post` and task runner. The fake
    runner calls the factory, so the handler's own arguments are what gets recorded."""
    calls: list[EnrichmentCall] = []

    def fake_propose(
        target: EnrichmentTarget, *, channel_id: str, requested_by: str | None = None
    ) -> None:
        calls.append(EnrichmentCall(str(target.role_id), channel_id, requested_by))

    def fake_run(coro_factory: Callable[[], Awaitable[None]], *, name: str) -> None:
        coro_factory()

    monkeypatch.setattr(handler_module, "propose_and_post", fake_propose)
    monkeypatch.setattr(handler_module._task_runner, "run", fake_run)
    return calls
