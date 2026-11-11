from datetime import UTC, datetime

from app.modules.interactions.domain.model import Channel, Direction, Role
from app.modules.interactions.domain.touch_building import (
    StoredItem,
    StoredParticipant,
    touches_by_organization,
)

INTERNAL = ("wusoolcapital.com", "dopaminecap.com")
WHEN = datetime(2026, 11, 5, 12, tzinfo=UTC)


def _item(mailbox: str, *participants: StoredParticipant, key: str = "k1") -> StoredItem:
    return StoredItem(mailbox, key, Channel.EMAIL, Direction.INBOUND, WHEN, "Hi", participants)


def _person(email: str, role: Role, org: str | None = "o1") -> StoredParticipant:
    return StoredParticipant(email, role, org)


def test_a_contact_on_both_to_and_cc_makes_one_touch() -> None:
    item = _item(
        "jules@wusoolcapital.com",
        _person("jules@wusoolcapital.com", Role.FROM),
        _person("sara@acme.com", Role.TO),
        _person("sara@acme.com", Role.CC),
    )

    (touch,) = touches_by_organization([item], INTERNAL)["o1"]

    assert (touch.team_member, touch.contact, touch.team_role) == (
        "jules@wusoolcapital.com",
        "sara@acme.com",
        Role.FROM,
    )


def test_an_alias_domain_mailbox_is_folded_before_finding_its_own_role() -> None:
    item = _item(
        "hugo@dopaminecap.com",
        _person("hugo@wusoolcapital.com", Role.CC),
        _person("sara@acme.com", Role.FROM),
    )

    (touch,) = touches_by_organization([item], INTERNAL)["o1"]

    assert (touch.team_member, touch.team_role) == ("hugo@wusoolcapital.com", Role.CC)


def test_internal_participants_and_unlinked_contacts_are_not_contacts() -> None:
    item = _item(
        "jules@wusoolcapital.com",
        _person("jules@wusoolcapital.com", Role.FROM, org="o1"),
        _person("ramzy@wusoolcapital.com", Role.TO, org="o1"),
        _person("stranger@nowhere.net", Role.TO, org=None),
    )

    assert touches_by_organization([item], INTERNAL) == {}


def test_an_owner_who_is_not_on_the_item_has_no_role() -> None:
    item = _item("jules@wusoolcapital.com", _person("sara@acme.com", Role.FROM))

    (touch,) = touches_by_organization([item], INTERNAL)["o1"]

    assert touch.team_role is None


def test_the_same_item_in_two_mailboxes_stays_two_touches_sharing_a_dedupe_key() -> None:
    sara = _person("sara@acme.com", Role.FROM)
    items = [_item("jules@wusoolcapital.com", sara), _item("ramzy@wusoolcapital.com", sara)]

    touches = touches_by_organization(items, INTERNAL)["o1"]

    assert {t.team_member for t in touches} == {
        "jules@wusoolcapital.com",
        "ramzy@wusoolcapital.com",
    }
    assert {t.dedupe_key for t in touches} == {"k1"}
