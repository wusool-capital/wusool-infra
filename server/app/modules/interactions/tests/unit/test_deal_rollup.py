"""A Deal's five fields, rolled up from its buyer and its seller."""

from collections.abc import Mapping, Sequence
from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.interactions.application.attio_write import AttioWriteConfig, AttioWriteService
from app.modules.interactions.application.ports.sent_values import RecordValues, SeedRow
from app.modules.interactions.domain.attio_fields import (
    FIELDS,
    AttioObject,
    FieldValue,
    WriteMode,
    fields_of,
    plan_record,
)
from app.modules.interactions.domain.deals import DealParties, deal_touches, merge_touches
from app.modules.interactions.domain.model import Channel, ScoringRules, Touch
from app.modules.interactions.persistence.score_store import _table
from app.modules.interactions.tests.fakes.touches import JULES, NOW

ORG, PERSON, DEAL = AttioObject.ORGANIZATIONS, AttioObject.PERSON, AttioObject.DEAL
SELLER_CONTACT = "sara@acme.com"
BUYER_CONTACT = "bob@beta.com"
FIVE = {
    "last_interaction_at",
    "next_interaction_at",
    "last_interaction_subject",
    "last_interaction_owner",
    "connection_strength",
}


def _touch(contact: str, days_ago: float, key: str | None = None) -> Touch:
    return Touch(
        key or f"{contact}-{days_ago}",
        JULES,
        contact,
        Channel.MEETING,
        None,
        NOW - timedelta(days=days_ago),
        "Call",
    )


class _Reader:
    def __init__(self, by_org: Mapping[str, tuple[Touch, ...]], by_person=None) -> None:
        self._by_org, self._by_person = by_org, by_person or {}

    async def touches_by_organization(self) -> Mapping[str, tuple[Touch, ...]]:
        return self._by_org

    async def touches_by_person(self) -> Mapping[str, tuple[Touch, ...]]:
        return self._by_person


class _Sent:
    def __init__(self, seeded: set[AttioObject], stored=None) -> None:
        self.seeded = seeded
        self.stored: dict[AttioObject, dict[str, RecordValues]] = stored or {}

    async def load(self, obj: AttioObject) -> Mapping[str, RecordValues]:
        return self.stored.setdefault(obj, {})

    async def save(self, obj: AttioObject, record_id: str, fields: Mapping[str, str]) -> None:
        old = self.stored.setdefault(obj, {}).get(record_id, RecordValues({}, {}))
        self.stored[obj][record_id] = RecordValues({**old.sent, **fields}, old.baseline)

    async def seed(self, obj: AttioObject, rows: Sequence[SeedRow]) -> int:
        return 0

    async def is_seeded(self, obj: AttioObject) -> bool:
        return obj in self.seeded

    async def mark_seeded(self, obj: AttioObject) -> None:
        self.seeded.add(obj)


class _Writer:
    def __init__(self) -> None:
        self.patches: list[tuple[AttioObject, str, dict[str, str | None]]] = []

    async def patch(self, obj: AttioObject, record_id: str, fields: Sequence[FieldValue]) -> None:
        self.patches.append((obj, record_id, {f.slug: f.value for f in fields}))

    def deal_patches(self) -> list[tuple[str, dict[str, str | None]]]:
        return [(rid, values) for obj, rid, values in self.patches if obj is DEAL]


class _Scores:
    """A Deal has no score column: any use of the store for one is a bug."""

    def __init__(self) -> None:
        self.saved: list[AttioObject] = []

    async def load(self, obj: AttioObject) -> Mapping[str, Decimal | None]:
        assert obj is not DEAL, "scores were read for a Deal"
        return {}

    async def save(self, obj: AttioObject, scores: Mapping[str, Decimal]) -> None:
        assert obj is not DEAL, "a score was saved for a Deal"
        self.saved.append(obj)


class _Deals:
    def __init__(self, *deals: DealParties) -> None:
        self.deals = deals

    async def load(self) -> tuple[DealParties, ...]:
        return self.deals


async def _members() -> Mapping[str, str]:
    return {JULES: "m-jules"}


DEAL_1 = DealParties("d1", "buyer-p", None, "seller-o")


def _service(
    sent: _Sent,
    writer: _Writer,
    *,
    by_org=None,
    by_person=None,
    deals: tuple[DealParties, ...] = (DEAL_1,),
    mode: WriteMode = WriteMode.ON,
    dry_run: bool = False,
    max_deals: int = 500,
) -> AttioWriteService:
    config = AttioWriteConfig(frozenset({JULES}), ScoringRules(), 500, dry_run, mode, max_deals)
    return AttioWriteService(
        _Reader(by_org or {}, by_person),
        sent,
        writer,
        _Scores(),
        _members,
        config,
        lambda: NOW,
        _Deals(*deals),
    )


def _seeded(**stored: dict[str, RecordValues]) -> _Sent:
    return _Sent({ORG, PERSON, DEAL}, {AttioObject(k): v for k, v in stored.items()})


async def test_a_deal_gets_only_its_five_fields_from_both_sides_together() -> None:
    sent, writer = _seeded(), _Writer()
    service = _service(
        sent,
        writer,
        by_org={"seller-o": (_touch(SELLER_CONTACT, 20),)},
        by_person={"buyer-p": (_touch(BUYER_CONTACT, 3),)},
    )

    report = await service.run_round()

    ((record, values),) = writer.deal_patches()
    assert record == "d1"
    assert set(values) <= FIVE
    # The buyer's meeting three days ago is later than the seller's, twenty days ago.
    assert values["last_interaction_at"] == (NOW - timedelta(days=3)).isoformat(
        timespec="milliseconds"
    )
    assert values["connection_strength"] is not None
    assert report.deals == 1


async def test_a_buyer_that_is_an_organization_counts_too() -> None:
    parties = DealParties("d1", None, "buyer-o", "seller-o")
    sent, writer = _seeded(), _Writer()
    service = _service(
        sent, writer, deals=(parties,), by_org={"buyer-o": (_touch(BUYER_CONTACT, 2),)}
    )

    await service.run_round()

    assert [r for r, _ in writer.deal_patches()] == ["d1"]


async def test_nothing_is_written_for_deals_while_the_rollup_is_off() -> None:
    sent, writer = _Sent({ORG, PERSON}), _Writer()
    service = _service(
        sent, writer, mode=WriteMode.OFF, by_org={"seller-o": (_touch(SELLER_CONTACT, 2),)}
    )

    report = await service.run_round()

    # Not seeded, yet not reported as unseeded: that would silence the stale-sync alarm.
    assert (writer.deal_patches(), report.unseeded) == ([], ())


async def test_an_unseeded_deal_writes_nothing_and_is_reported() -> None:
    sent, writer = _Sent({ORG, PERSON}), _Writer()
    service = _service(sent, writer, by_org={"seller-o": (_touch(SELLER_CONTACT, 2),)})

    report = await service.run_round()

    assert writer.deal_patches() == []
    assert report.unseeded == (DEAL,)


async def test_the_deal_rollup_can_dry_run_while_the_rest_writes() -> None:
    sent, writer = _seeded(), _Writer()
    service = _service(
        sent,
        writer,
        mode=WriteMode.DRY_RUN,
        by_org={"seller-o": (_touch(SELLER_CONTACT, 2),), "o1": (_touch("x@y.com", 1),)},
    )

    report = await service.run_round()

    assert writer.deal_patches() == []
    assert [rid for obj, rid, _ in writer.patches if obj is ORG] == ["o1", "seller-o"]
    assert report.deals == 1  # counted as it would be, not sent


async def test_deals_have_their_own_cap() -> None:
    parties = (DealParties("d1", None, None, "o1"), DealParties("d2", None, None, "o2"))
    sent, writer = _seeded(), _Writer()
    service = _service(
        sent,
        writer,
        deals=parties,
        max_deals=1,
        by_org={"o1": (_touch(SELLER_CONTACT, 2),), "o2": (_touch(BUYER_CONTACT, 2),)},
    )

    report = await service.run_round()

    assert [r for r, _ in writer.deal_patches()] == ["d1"]
    assert report.hit_cap is True


async def test_a_deal_never_touches_the_score_store() -> None:
    sent, writer = _seeded(), _Writer()
    service = _service(sent, writer, by_org={"seller-o": (_touch(SELLER_CONTACT, 2),)})

    await service.run_round()  # the fake raises if a Deal's score is read or saved

    assert writer.deal_patches() != []


async def test_a_deal_whose_party_was_led_by_an_unread_mailbox_keeps_its_strength() -> None:
    stored = {
        "organizations": {
            "seller-o": RecordValues({}, {"strongest_connection_user": "m-hugo"}),
        },
    }
    sent, writer = _seeded(**stored), _Writer()
    service = _service(sent, writer, by_org={"seller-o": (_touch(SELLER_CONTACT, 2),)})

    await service.run_round()

    ((_, values),) = writer.deal_patches()
    assert "connection_strength" not in values
    assert "last_interaction_at" in values


async def test_a_deal_that_went_quiet_fades_to_the_lowest_label_and_loses_its_next_date() -> None:
    held = {
        "last_interaction_at": "2026-10-01T00:00:00.000+00:00",
        "next_interaction_at": "2026-11-20T00:00:00.000+00:00",
        "connection_strength": "Strong",
    }
    sent = _seeded(deal={"d1": RecordValues(held, {})})
    writer = _Writer()

    await _service(sent, writer).run_round()

    ((_, values),) = writer.deal_patches()
    assert values == {"next_interaction_at": None, "connection_strength": "Very weak"}


def test_a_touch_that_reaches_both_sides_counts_once() -> None:
    shared = _touch(SELLER_CONTACT, 2, key="same-email")

    assert merge_touches([(shared,), (shared,), (_touch(BUYER_CONTACT, 5),)]) == (
        shared,
        _touch(BUYER_CONTACT, 5),
    )


def test_deals_with_no_touches_are_left_out() -> None:
    touches = deal_touches(
        [DEAL_1, DealParties("d2", None, None, "quiet")],
        {"seller-o": (_touch(SELLER_CONTACT, 2),)},
        {},
    )

    assert set(touches) == {"d1"}


def test_a_deal_has_five_of_the_thirteen_fields() -> None:
    assert {s.slug for s in fields_of(DEAL)} == FIVE
    assert fields_of(ORG) == FIELDS == fields_of(PERSON)


def test_plan_record_writes_only_the_fields_it_is_given() -> None:
    computed = {slug: "x" for slug in (s.slug for s in FIELDS)}

    plan = plan_record(computed, {}, {}, frozenset(), fields_of(DEAL))

    assert {w.slug for w in plan.writes} <= FIVE


def test_the_score_store_refuses_an_object_without_a_score_column() -> None:
    with pytest.raises(ValueError, match="no connection strength score column"):
        _table(DEAL)
