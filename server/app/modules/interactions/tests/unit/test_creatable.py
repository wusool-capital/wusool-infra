import pytest

from app.modules.interactions.domain.creatable import is_creatable, is_no_reply_address

FREE = frozenset({"gmail.com", "yahoo.com"})


def _creatable(address: str = "sara@acme.com", **overrides: bool) -> bool:
    flags = {"has_list_unsubscribe": False, "two_way_thread": True, "attended_meeting": False}
    flags.update(overrides)
    return is_creatable(address, free_email_domains=FREE, **flags)


def test_a_two_way_thread_with_an_outside_company_creates() -> None:
    assert _creatable()


def test_an_attended_meeting_creates_without_any_email() -> None:
    assert _creatable(two_way_thread=False, attended_meeting=True)


def test_one_way_mail_alone_never_creates() -> None:
    assert not _creatable(two_way_thread=False)


@pytest.mark.parametrize("address", ["hugo@wusoolcapital.com", "hugo@dopaminecap.com"])
def test_internal_addresses_never_create(address: str) -> None:
    assert not _creatable(address)


def test_free_email_domains_never_create() -> None:
    assert not _creatable("sara@gmail.com")


def test_bulk_senders_never_create_even_in_a_two_way_thread() -> None:
    assert not _creatable(has_list_unsubscribe=True)


@pytest.mark.parametrize("local", ["noreply", "no-reply", "donotreply", "do-not-reply"])
def test_no_reply_senders_never_create(local: str) -> None:
    assert is_no_reply_address(f"{local}@acme.com")
    assert not _creatable(f"{local}@acme.com")


def test_a_person_whose_name_contains_reply_is_not_a_no_reply_sender() -> None:
    assert not is_no_reply_address("replyall@acme.com")
