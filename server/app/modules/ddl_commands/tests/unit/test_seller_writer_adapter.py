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
from app.modules.discovery import (
    CrmMatchKind,
    DiscoveredLead,
    SellerDraft,
    SellerWriteError,
    UnverifiedSeller,
)
from app.modules.enrichment import (
    BasicEnrichment,
    ProposedFieldValue,
    ProviderEvidence,
    WriteTarget,
)


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


def _enriched(website: str | None) -> BasicEnrichment:
    return BasicEnrichment(
        values=(_proposed("employee_range", "11-50", WriteTarget.ORGANIZATION),),
        evidence=(ProviderEvidence("Diffbot", website, ("employee_range",)),),
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
    async def _enrich(**kwargs: object) -> BasicEnrichment:
        assert kwargs["domain"] == "acme.example"
        return _enriched(website="https://www.acme.example/")

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
    async def _slow(**kwargs: object) -> BasicEnrichment:
        await asyncio.sleep(1)
        return BasicEnrichment(values=())

    monkeypatch.setattr(module, "propose_basic_seller_fields", _slow)

    created = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        _draft(), enrichment_timeout_s=0.01
    )

    assert len(write) == 1
    assert created.enrichment_timed_out is True


async def test_exhausted_budget_skips_enrichment(monkeypatch, write) -> None:
    async def _never(**kwargs: object) -> BasicEnrichment:
        raise AssertionError("must not enrich with no budget left")

    monkeypatch.setattr(module, "propose_basic_seller_fields", _never)

    created = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        _draft(), enrichment_timeout_s=0
    )

    assert len(write) == 1
    assert created.enrichment_timed_out is True


async def test_enrichment_error_does_not_block_the_write(monkeypatch, write) -> None:
    async def _boom(**kwargs: object) -> BasicEnrichment:
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
    monkeypatch.setattr(
        module, "propose_basic_seller_fields", _returning(BasicEnrichment(values=()))
    )

    with pytest.raises(SellerWriteError) as exc_info:
        await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
            _draft(), enrichment_timeout_s=5
        )

    assert exc_info.value.landed == ("organization 'Acme Co' created in Attio",)


async def test_domain_created_since_the_lookup_aborts_the_write(monkeypatch, write) -> None:
    monkeypatch.setattr(module, "find_organization_by_domains", _returning(_org()))
    monkeypatch.setattr(
        module, "propose_basic_seller_fields", _returning(BasicEnrichment(values=()))
    )

    # A branch of the same company: different place id, same website.
    with pytest.raises(SellerWriteError, match="already in the CRM"):
        await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
            SellerDraft(
                org_name="Acme Branch",
                values={"domains": ["acme.example"]},
                source_place_id="p2",
            ),
            enrichment_timeout_s=5,
        )

    assert write == []


async def test_enrichment_runs_outside_the_write_lock(monkeypatch, write) -> None:
    adapter = module.DdlCommandsSellerWriterAdapter()
    inside_enrichment: list[bool] = []

    async def _enrich(**kwargs: object) -> BasicEnrichment:
        inside_enrichment.append(adapter._write_lock.locked())
        return BasicEnrichment(values=())

    monkeypatch.setattr(module, "propose_basic_seller_fields", _enrich)

    await adapter.enrich_and_create(_draft(), enrichment_timeout_s=5)

    assert inside_enrichment == [False]


@pytest.mark.parametrize("provider_website", ["acme-group.de", None])
async def test_unverified_provider_website_returns_for_review(
    monkeypatch, write, provider_website: str | None
) -> None:
    monkeypatch.setattr(
        module, "propose_basic_seller_fields", _returning(_enriched(provider_website))
    )

    result = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        _draft(), enrichment_timeout_s=5
    )

    assert write == []
    assert isinstance(result, UnverifiedSeller)
    assert result.maps_website == "acme.example"
    assert result.provider_websites == (("Diffbot", provider_website),)
    assert [(v.field_name, v.value) for v in result.values] == [("employee_range", "11-50")]
    assert result.draft.values["employee_range"] == "11-50"
    assert result.draft.source_place_id == "p1"


async def test_no_maps_website_with_provider_fields_returns_for_review(monkeypatch, write) -> None:
    """Diffbot matched on name alone, so nothing anchors it to this lead."""
    monkeypatch.setattr(
        module, "propose_basic_seller_fields", _returning(_enriched("acme.example"))
    )

    result = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        SellerDraft(org_name="Acme Co", source_place_id="p1"), enrichment_timeout_s=5
    )

    assert write == []
    assert isinstance(result, UnverifiedSeller)
    assert result.maps_website is None


async def test_a_provider_whose_fields_were_all_dropped_is_not_checked(monkeypatch, write) -> None:
    """PDL's only field is out of vocabulary, so its missing website is moot."""
    enrichment = BasicEnrichment(
        values=(
            _proposed("employee_range", "11-50", WriteTarget.ORGANIZATION),
            _proposed("sector_focus", ["Not A Sector"], WriteTarget.ORGANIZATION),
        ),
        evidence=(
            ProviderEvidence("Diffbot", "acme.example", ("employee_range",)),
            ProviderEvidence("People Data Labs", None, ("sector_focus",)),
        ),
    )
    monkeypatch.setattr(module, "propose_basic_seller_fields", _returning(enrichment))

    created = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        _draft(), enrichment_timeout_s=5
    )

    assert len(write) == 1
    assert created.enriched_fields == ("employee_range",)


async def test_an_invalid_value_from_an_unverified_provider_goes_to_review(
    monkeypatch, write
) -> None:
    """Validation runs after the website check, so a wrong company's bad value
    reaches a human instead of failing the lead."""
    enrichment = BasicEnrichment(
        values=(_proposed("description", "x" * 5000, WriteTarget.ORGANIZATION),),
        evidence=(ProviderEvidence("Diffbot", "other.example", ("description",)),),
    )
    monkeypatch.setattr(module, "propose_basic_seller_fields", _returning(enrichment))

    result = await module.DdlCommandsSellerWriterAdapter().enrich_and_create(
        _draft(), enrichment_timeout_s=5
    )

    assert write == []
    assert isinstance(result, UnverifiedSeller)
