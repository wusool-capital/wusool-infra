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
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs


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
        return SubjectRefs(
            org_attio_id=kwargs.get("organization_attio_id") or "org-new",
            org_name=kwargs["organization_name"],
        )

    async def write_buyer_role(self, **kwargs):
        self.buyer_calls.append(kwargs)
        return SubjectRefs(
            org_attio_id=kwargs.get("organization_attio_id") or "org-new",
            org_name=kwargs["organization_name"],
        )


class _FakePersonWriter:
    """Defaults to "nothing to write" (`None`) so every pre-existing test
    stays about organisation dedup, not the person write."""

    def __init__(self, *, result: tuple[str, str] | None = None, raises: bool = False) -> None:
        self.calls: list[dict] = []
        self._result = result
        self._raises = raises

    async def write(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise RuntimeError("Attio 503")
        return self._result


class _FakeDealWriter:
    """Defaults to "nothing written" (`None`) so every pre-existing test
    stays about organisation dedup, not the deal write."""

    def __init__(self, *, result: str | None = None, raises: bool = False) -> None:
        self.calls: list[dict] = []
        self._result = result
        self._raises = raises

    async def write(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise RuntimeError("Attio 503")
        return self._result


async def test_write_reuses_an_existing_org_matched_by_name_and_domain() -> None:
    organizations = _FakeOrganizations([_Candidate(attio_id="org-1", domains=["acme.com"])])
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        writer, organizations, _FakePersonWriter(), _FakeDealWriter()
    )

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
    role_attio_writer = bootstrap._RoleAttioWriter(
        writer, organizations, _FakePersonWriter(), _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="valuation", payload={"company": "Acme", "domain": "acme.com"}, ai={}
    )

    assert writer.seller_calls[0]["organization_attio_id"] is None


async def test_write_skips_dedup_entirely_when_no_domain_given() -> None:
    """Matching on name alone risks merging two distinct companies — never
    attempted, and `search_by_name` isn't even called."""
    organizations = _FakeOrganizations([_Candidate(attio_id="org-1", domains=["acme.com"])])
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        writer, organizations, _FakePersonWriter(), _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="valuation", payload={"company": "Acme", "domain": None}, ai={}
    )

    assert writer.seller_calls[0]["organization_attio_id"] is None
    assert organizations.searched_for == []


async def test_write_dedups_buyer_role_the_same_way() -> None:
    organizations = _FakeOrganizations([_Candidate(attio_id="org-1", domains=["acme.com"])])
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        writer, organizations, _FakePersonWriter(), _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="buyer_network", payload={"org_name": "Acme", "domain": "acme.com"}, ai={}
    )

    assert writer.buyer_calls[0]["organization_attio_id"] == "org-1"


async def test_write_prefers_sector_over_peer_key_for_tech_mode_benchmark() -> None:
    """Tech-mode benchmark's `peer_key` is a funding stage ("seed"), not a
    sector — `sector_mapping.py` has no entry for it, so passing `peer_key`
    as the CRM sector raised `UnmappedSectorError` on every real tech-mode
    submission. The form now also sends `sector` (the real tech sector);
    this pins that it wins over `peer_key` when both are present."""
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        writer, _FakeOrganizations([]), _FakePersonWriter(), _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="benchmark",
        payload={"company": "Acme", "mode": "tech", "peer_key": "seed", "sector": "AI"},
        ai={},
    )

    assert writer.seller_calls[0]["sector"] == "AI"


async def test_write_falls_back_to_peer_key_for_sme_mode_benchmark() -> None:
    """SME mode never sends a separate `sector` — `peer_key` there already
    is the CRM sector, and must still be used."""
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        writer, _FakeOrganizations([]), _FakePersonWriter(), _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="benchmark",
        payload={"company": "Acme", "mode": "sme", "peer_key": "itservices"},
        ai={},
    )

    assert writer.seller_calls[0]["sector"] == "itservices"


async def test_write_rejects_a_non_string_org_type_entry() -> None:
    """`payload` is now parsed through `BuyerNetworkPayload` rather than a
    manual `isinstance` filter — a malformed stored row now fails loudly
    instead of silently dropping the bad entry, matching this module's
    established "raise rather than default" rule (`UnmappedSectorError`)."""
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(), _FakeOrganizations([]), _FakePersonWriter(), _FakeDealWriter()
    )

    with pytest.raises(ValidationError):
        await role_attio_writer.write(
            tool="buyer_network",
            payload={"org_name": "Acme", "org_type": ["PE Fund", 123]},
            ai={},
        )


async def test_write_resolves_person_name_per_tool() -> None:
    """Benchmark/valuation read an optional `name`; readiness's is required
    at the API but still flows through the same `AttioIdentityPayload.name`
    field; buyer_network reads its own `full_name`."""
    person = _FakePersonWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(), _FakeOrganizations([]), person, _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="benchmark",
        payload={
            "company": "Acme",
            "peer_key": "itservices",
            "name": "Dana",
            "email": "d@acme.com",
        },
        ai={},
    )
    await role_attio_writer.write(
        tool="readiness",
        payload={"company": "Acme", "name": "Sam", "email": "s@acme.com"},
        ai={},
    )
    await role_attio_writer.write(
        tool="buyer_network",
        payload={"org_name": "Acme", "full_name": "Robin", "email": "r@acme.com"},
        ai={},
    )

    assert [call["name"] for call in person.calls] == ["Dana", "Sam", "Robin"]


async def test_write_person_name_is_blank_when_not_collected() -> None:
    """Benchmark/valuation don't require a name from the visitor —
    `AttioIdentityPayload.name` defaults to `""` (same default as its
    other optional fields), and `AttioPersonWriter` (not this seam) is
    what falls back to the email for a blank name."""
    person = _FakePersonWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(), _FakeOrganizations([]), person, _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="valuation", payload={"company": "Acme", "email": "v@acme.com"}, ai={}
    )

    assert person.calls[0]["name"] == ""


async def test_write_passes_the_just_written_org_id_to_the_person_writer() -> None:
    organizations = _FakeOrganizations([_Candidate(attio_id="org-1", domains=["acme.com"])])
    person = _FakePersonWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(), organizations, person, _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="valuation",
        payload={"company": "Acme", "domain": "acme.com", "email": "v@acme.com"},
        ai={},
    )

    assert person.calls[0]["organization_attio_id"] == "org-1"


async def test_write_passes_benchmarks_phone_to_the_person_writer() -> None:
    """`phone` is benchmark-only — no other tool's form asks for it, so
    every other tool's call must pass `None` rather than error."""
    person = _FakePersonWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(), _FakeOrganizations([]), person, _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="benchmark",
        payload={
            "company": "Acme",
            "peer_key": "itservices",
            "email": "d@acme.com",
            "phone": "+971500000000",
        },
        ai={},
    )
    await role_attio_writer.write(
        tool="valuation", payload={"company": "Acme", "email": "v@acme.com"}, ai={}
    )

    assert person.calls[0]["phone"] == "+971500000000"
    assert person.calls[1]["phone"] is None


async def test_write_survives_a_person_write_failure() -> None:
    """A person-write failure must not lose the org/role write that already
    landed, and must not propagate to the caller — see this module's
    README, "Person dedupe"."""
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(), _FakeOrganizations([]), _FakePersonWriter(raises=True), _FakeDealWriter()
    )

    subjects = await role_attio_writer.write(
        tool="valuation", payload={"company": "Acme", "email": "v@acme.com"}, ai={}
    )

    assert subjects.org_attio_id is not None
    assert subjects.person_attio_id is None


async def test_write_fills_in_person_refs_on_success() -> None:
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(),
        _FakeOrganizations([]),
        _FakePersonWriter(result=("person-1", "Dana")),
        _FakeDealWriter(),
    )

    subjects = await role_attio_writer.write(
        tool="valuation",
        payload={"company": "Acme", "email": "v@acme.com", "name": "Dana"},
        ai={},
    )

    assert subjects.person_attio_id == "person-1"
    assert subjects.person_name == "Dana"
    # Org/role refs from the writer are preserved, not clobbered.
    assert subjects.org_attio_id is not None


async def test_write_passes_capital_raised_and_readiness_country_through() -> None:
    """`capital_raised` -> `organizations.funding_raised`; readiness's own
    `country` field reaches `hq_country` the same way benchmark/valuation's
    `geography` already does."""
    writer = _FakeRoleWriter()
    role_attio_writer = bootstrap._RoleAttioWriter(
        writer, _FakeOrganizations([]), _FakePersonWriter(), _FakeDealWriter()
    )

    await role_attio_writer.write(
        tool="benchmark",
        payload={"company": "Acme", "peer_key": "itservices", "capital_raised": 250000.0},
        ai={},
    )
    await role_attio_writer.write(
        tool="readiness", payload={"company": "Acme", "country": "United Arab Emirates"}, ai={}
    )

    assert writer.seller_calls[0]["funding_raised"] == 250000.0
    assert writer.seller_calls[1]["hq_country"] == "United Arab Emirates"


async def test_write_picks_the_deal_side_from_the_tool() -> None:
    """A seller tool's visitor is the company that might sell; a
    buyer-network applicant is the acquirer."""
    deal = _FakeDealWriter(result="deal-1")
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(), _FakeOrganizations([]), _FakePersonWriter(), deal
    )

    await role_attio_writer.write(tool="valuation", payload={"company": "Acme"}, ai={})
    await role_attio_writer.write(tool="readiness", payload={"company": "Acme"}, ai={})
    await role_attio_writer.write(
        tool="benchmark", payload={"company": "Acme", "peer_key": "itservices"}, ai={}
    )
    await role_attio_writer.write(tool="buyer_network", payload={"org_name": "Fund"}, ai={})

    assert [call["deal_type"] for call in deal.calls] == [
        "Sell-side",
        "Sell-side",
        "Sell-side",
        "Buy-side",
    ]


async def test_write_fills_in_the_deal_ref_on_success() -> None:
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(),
        _FakeOrganizations([_Candidate(attio_id="org-1", domains=["acme.com"])]),
        _FakePersonWriter(),
        _FakeDealWriter(result="deal-1"),
    )

    subjects = await role_attio_writer.write(
        tool="valuation", payload={"company": "Acme", "domain": "acme.com"}, ai={}
    )

    assert subjects.deal_attio_id == "deal-1"
    assert subjects.org_attio_id == "org-1"


async def test_write_survives_a_deal_write_failure() -> None:
    """Same rule as the person write: the org/role write already landed the
    lead, and a deal failure must not propagate to the caller."""
    role_attio_writer = bootstrap._RoleAttioWriter(
        _FakeRoleWriter(),
        _FakeOrganizations([]),
        _FakePersonWriter(),
        _FakeDealWriter(raises=True),
    )

    subjects = await role_attio_writer.write(tool="valuation", payload={"company": "Acme"}, ai={})

    assert subjects.org_attio_id is not None
    assert subjects.deal_attio_id is None
