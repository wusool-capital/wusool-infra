"""`run_sweeper_forever`'s loop behaviour: a failed pass must not kill the
loop, and cancellation (how `main.py`'s lifespan stops it on shutdown) must
actually propagate rather than being swallowed. Also `_RoleAttioWriter`'s
Postgres-side org dedup: without it, every submission from a company Attio
has already seen creates a second Attio organisation.
"""

import asyncio
from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from app.modules.lead_magnets import bootstrap


class _FakeSettings:
    lead_magnet_sweeper_interval_s = 0
    lead_magnet_sweeper_stale_after_s = 300


class _FakeSessionCtx:
    async def __aenter__(self):
        class _Session:
            async def commit(self) -> None:
                pass

        return _Session()

    async def __aexit__(self, *exc: object) -> bool:
        return False


async def test_loop_survives_a_failed_pass_and_stops_on_cancel(monkeypatch) -> None:
    calls: list[int] = []

    async def fake_sweep_once(tool_runs, submissions, *, stale_after_s):
        calls.append(stale_after_s)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return 0

    monkeypatch.setattr(bootstrap, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(bootstrap, "get_sessionmaker", lambda: _FakeSessionCtx)
    monkeypatch.setattr(bootstrap, "build_tool_runs", lambda session: object())
    monkeypatch.setattr(bootstrap, "build_submission_service", lambda session: object())
    monkeypatch.setattr(bootstrap, "sweep_once", fake_sweep_once)

    task = asyncio.create_task(bootstrap.run_sweeper_forever())
    for _ in range(1000):
        if len(calls) >= 3:
            break
        await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(calls) >= 3, "a RuntimeError on one pass must not stop later passes"


@dataclass
class _Candidate:
    attio_id: str
    domains: list[str] = field(default_factory=list)


class _FakeOrganizations:
    def __init__(self, candidates: list[_Candidate]) -> None:
        self._candidates = candidates
        self.searched_for: list[str] = []

    async def search_by_name(self, term: str) -> list[_Candidate]:
        self.searched_for.append(term)
        return self._candidates


class _FakeRoleWriter:
    def __init__(self) -> None:
        self.seller_calls: list[dict] = []
        self.buyer_calls: list[dict] = []

    async def write_seller_role(self, **kwargs):
        self.seller_calls.append(kwargs)
        return object()

    async def write_buyer_role(self, **kwargs):
        self.buyer_calls.append(kwargs)
        return object()


async def test_write_reuses_an_existing_org_matched_by_name_and_domain() -> None:
    organizations = _FakeOrganizations([_Candidate(attio_id="org-1", domains=["acme.com"])])
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(writer, organizations)

    await role_attio_writer.write(
        tool="valuation",
        payload={"company": "Acme Trading LLC", "domain": "https://www.acme.com"},
        ai={},
    )

    assert writer.seller_calls[0]["organization_attio_id"] == "org-1"
    assert organizations.searched_for == ["acme trading"]


async def test_write_creates_new_when_no_domain_matches() -> None:
    """A name-similarity hit with no matching domain is a different company,
    not the same one under a new domain."""
    organizations = _FakeOrganizations([_Candidate(attio_id="org-1", domains=["other.com"])])
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(writer, organizations)

    await role_attio_writer.write(
        tool="valuation", payload={"company": "Acme", "domain": "acme.com"}, ai={}
    )

    assert writer.seller_calls[0]["organization_attio_id"] is None


async def test_write_skips_dedup_entirely_when_no_domain_given() -> None:
    """Matching on name alone risks merging two distinct companies — never
    attempted, and `search_by_name` isn't even called."""
    organizations = _FakeOrganizations([_Candidate(attio_id="org-1", domains=["acme.com"])])
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(writer, organizations)

    await role_attio_writer.write(
        tool="valuation", payload={"company": "Acme", "domain": None}, ai={}
    )

    assert writer.seller_calls[0]["organization_attio_id"] is None
    assert organizations.searched_for == []


async def test_write_dedups_buyer_role_the_same_way() -> None:
    organizations = _FakeOrganizations([_Candidate(attio_id="org-1", domains=["acme.com"])])
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(writer, organizations)

    await role_attio_writer.write(
        tool="buyer_network", payload={"org_name": "Acme", "domain": "acme.com"}, ai={}
    )

    assert writer.buyer_calls[0]["organization_attio_id"] == "org-1"


async def test_write_rejects_a_non_string_org_type_entry() -> None:
    """`payload` is now parsed through `BuyerNetworkPayload` rather than a
    manual `isinstance` filter — a malformed stored row now fails loudly
    instead of silently dropping the bad entry, matching this module's
    established "raise rather than default" rule (`UnmappedSectorError`)."""
    role_attio_writer = bootstrap._RoleAttioWriter(_FakeRoleWriter(), _FakeOrganizations([]))

    with pytest.raises(ValidationError):
        await role_attio_writer.write(
            tool="buyer_network",
            payload={"org_name": "Acme", "org_type": ["PE Fund", 123]},
            ai={},
        )
