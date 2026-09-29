"""Unit coverage for `DdlCommandsSellerWriterAdapter` — the CRM pre-filter
lookup order and the enrich-then-write-once create. Every collaborator
(DB lookups, enrichment, the Attio-first write) is faked.
"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.providers.discovery import seller_writer_adapter as module
from app.modules.discovery import CrmMatchKind, DiscoveredLead, SellerDraft, SellerWriteError
from app.modules.enrichment import ProposedFieldValue, WriteTarget


def _org(attio_id: str = "org-1", name: str = "Acme Holdings") -> SimpleNamespace:
    return SimpleNamespace(attio_id=attio_id, name=name)


def _proposed(name: str, value: object, target: WriteTarget) -> ProposedFieldValue:
    return ProposedFieldValue(
        field_name=name,
        write_target=target,
        current=None,
        proposed=value,  # ty: ignore[invalid-argument-type]
        source_url="https://diffbot.example",
        confidence=0.9,
        rationale="Sourced from Diffbot.",
    )


def _returning(value: object):
    async def _fn(*args: object, **kwargs: object) -> object:
        return value

    return _fn


@pytest.fixture
def lookups(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "find_organization_by_place_id", _returning(None))
    monkeypatch.setattr(module, "find_organization_by_domains", _returning(None))
    monkeypatch.setattr(module, "search_organizations", _returning([]))


LEAD = DiscoveredLead(
    name="Acme Co", source_url="https://maps.example/a", website="https://www.Acme.example/x",
    place_id="p1",
)  # fmt: skip


async def test_place_id_match_wins_over_everything(monkeypatch, lookups) -> None:
    monkeypatch.setattr(module, "find_organization_by_place_id", _returning(_org()))

    match = await module.DdlCommandsSellerWriterAdapter().find_existing(LEAD)

    assert match.kind is CrmMatchKind.PLACE_ID
    assert match.org_name == "Acme Holdings"


async def test_domain_match_checks_bare_and_www_variants(monkeypatch, lookups) -> None:
    seen: list[list[str]] = []

    async def _by_domains(hosts: list[str]) -> SimpleNamespace:
        seen.append(hosts)
        return _org()

    monkeypatch.setattr(module, "find_organization_by_domains", _by_domains)

    match = await module.DdlCommandsSellerWriterAdapter().find_existing(LEAD)

    assert match.kind is CrmMatchKind.DOMAIN
    assert seen == [["acme.example", "www.acme.example"]]


async def test_name_only_hit_is_fuzzy(monkeypatch, lookups) -> None:
    monkeypatch.setattr(module, "search_organizations", _returning([_org(name="Acme Trading")]))

    match = await module.DdlCommandsSellerWriterAdapter().find_existing(LEAD)

    assert match.kind is CrmMatchKind.FUZZY_NAME
    assert match.org_name == "Acme Trading"


async def test_no_hit_is_none(lookups) -> None:
    match = await module.DdlCommandsSellerWriterAdapter().find_existing(LEAD)

    assert match.kind is CrmMatchKind.NONE


def _draft(**extra: object) -> SellerDraft:
    return SellerDraft(
        org_name="Acme Co",
        values={"hq_country": "United Arab Emirates", "domains": ["acme.example"]},
        source_urls=("https://maps.example/a",),
        source_place_id="p1",
        **extra,  # ty: ignore[invalid-argument-type]
    )


@pytest.fixture
def write(monkeypatch: pytest.MonkeyPatch, lookups) -> list[dict]:
    calls: list[dict] = []

    async def _write(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(id=uuid.uuid4(), org_attio_id="new-org")

    monkeypatch.setattr(module, "write_seller_add", _write)
    return calls


async def test_creates_once_with_enrichment_and_place_id(monkeypatch, write) -> None:
    async def _enrich(**kwargs: object) -> tuple[ProposedFieldValue, ...]:
        assert kwargs["domain"] == "acme.example"
        return (_proposed("employee_range", "11-50", WriteTarget.ORGANIZATION),)

    monkeypatch.setattr(module, "propose_basic_seller_fields", _enrich)

    created = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        _draft(), enrichment_timeout_s=5
    )

    assert len(write) == 1
    assert write[0]["source_place_id"] == "p1"
    assert write[0]["is_new_org"] is True
    assert write[0]["org_extracted"]["employee_range"] == "11-50"
    assert write[0]["org_extracted"]["hq_country"] == "United Arab Emirates"
    assert created.org_attio_id == "new-org"
    assert created.enriched_fields == ("employee_range",)
    assert created.enrichment_timed_out is False


async def test_enrichment_timeout_still_writes_the_lead(monkeypatch, write) -> None:
    async def _slow(**kwargs: object) -> tuple[ProposedFieldValue, ...]:
        await asyncio.sleep(1)
        return ()

    monkeypatch.setattr(module, "propose_basic_seller_fields", _slow)

    created = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        _draft(), enrichment_timeout_s=0.01
    )

    assert len(write) == 1
    assert created.enrichment_timed_out is True


async def test_exhausted_budget_skips_enrichment(monkeypatch, write) -> None:
    async def _never(**kwargs: object) -> tuple[ProposedFieldValue, ...]:
        raise AssertionError("must not enrich with no budget left")

    monkeypatch.setattr(module, "propose_basic_seller_fields", _never)

    created = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        _draft(), enrichment_timeout_s=0
    )

    assert len(write) == 1
    assert created.enrichment_timed_out is True


async def test_enrichment_error_does_not_block_the_write(monkeypatch, write) -> None:
    async def _boom(**kwargs: object) -> tuple[ProposedFieldValue, ...]:
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(module, "propose_basic_seller_fields", _boom)

    created = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        _draft(), enrichment_timeout_s=5
    )

    assert len(write) == 1
    assert created.enriched_fields == ()


async def test_place_id_created_since_the_lookup_aborts_the_write(monkeypatch, write) -> None:
    monkeypatch.setattr(module, "find_organization_by_place_id", _returning(_org()))

    with pytest.raises(SellerWriteError, match="already in the CRM"):
        await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
            _draft(), enrichment_timeout_s=5
        )

    assert write == []


async def test_partial_write_reports_what_landed(monkeypatch, lookups) -> None:
    async def _fail(**kwargs: object) -> object:
        raise PartialWriteError(["organization 'Acme Co' created in Attio"], RuntimeError("db"))

    monkeypatch.setattr(module, "write_seller_add", _fail)
    monkeypatch.setattr(module, "propose_basic_seller_fields", _returning(()))

    with pytest.raises(SellerWriteError) as exc_info:
        await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
            _draft(), enrichment_timeout_s=5
        )

    assert exc_info.value.landed == ("organization 'Acme Co' created in Attio",)
