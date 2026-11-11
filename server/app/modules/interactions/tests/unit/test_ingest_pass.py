from dataclasses import replace

from app.modules.google_workspace import CalendarPage, MailPage
from app.modules.interactions.application.ports.interaction_store import Source
from app.modules.interactions.domain.linking import PersonRef, RecordDirectory
from app.modules.interactions.domain.windows import months_before
from app.modules.interactions.tests.fakes.ingest import (
    CONFIG,
    FakeCalendar,
    FakeDirectory,
    FakeMail,
    FakeStore,
    make_service,
    message,
)
from app.modules.interactions.tests.fakes.touches import JULES, NOW, RAMZY, SARA


async def test_one_failing_mailbox_does_not_stop_the_others() -> None:
    store, mail, calendar = FakeStore(), FakeMail(), FakeCalendar()
    mail.fail_for = {JULES}
    config = replace(CONFIG, mailboxes=(JULES, RAMZY))
    mail.backfill_pages = [MailPage((message("r1", to=(RAMZY,)),), None)]
    # One calendar page for each mailbox.
    calendar.backfill_pages = [CalendarPage((), None, "s1"), CalendarPage((), None, "s2")]

    report = await make_service(store, mail, calendar, config=config).run_pass()

    assert report.failures == (f"{JULES}:gmail",)
    assert (RAMZY, Source.GMAIL) in store.cursors
    # The failing mailbox's calendar is a separate source and still ran.
    assert (JULES, Source.CALENDAR) in store.cursors
    assert (JULES, Source.GMAIL) not in store.cursors


async def test_a_linking_failure_is_reported_and_does_not_lose_what_was_saved() -> None:
    store, mail = FakeStore(), FakeMail()
    mail.backfill_pages = [MailPage((message("m1"), message("m2")), None)]
    directory = FakeDirectory(fails=True)

    report = await make_service(store, mail, directory=directory).run_pass()

    assert report.failures == ("linking",)
    assert report.written == 2
    assert [i.source_id for i in store.items] == ["m1", "m2"]


async def test_a_clean_pass_reports_no_failures_and_what_it_wrote() -> None:
    store, mail = FakeStore(), FakeMail()
    mail.backfill_pages = [MailPage((message("m1"), message("m2")), None)]

    report = await make_service(store, mail).run_pass()

    assert report.failures == ()
    assert report.written == 2


async def test_outside_addresses_are_linked_to_the_records_that_match_them() -> None:
    store, mail = FakeStore(), FakeMail()
    mail.backfill_pages = [
        MailPage(
            (
                message("m1", sender=SARA),
                message("m2", sender="new@acme.com"),
                message("m3", sender="stranger@elsewhere.org"),
            ),
            None,
        )
    ]
    directory = FakeDirectory(
        RecordDirectory(
            people_by_email={SARA: (PersonRef("p1", "o1"),)},
            org_ids_by_domain={"acme.com": ("o1",)},
        )
    )

    report = await make_service(store, mail, directory=directory).run_pass()

    assert report.linked == 2
    assert store.links[SARA].person_id == "p1"
    assert store.links[SARA].organization_id == "o1"
    # No Person yet, but the domain is known, so the Organization still links.
    assert (store.links["new@acme.com"].person_id, store.links["new@acme.com"].organization_id) == (
        None,
        "o1",
    )
    assert "stranger@elsewhere.org" not in store.links


async def test_an_address_shared_by_several_persons_is_counted_and_left_unlinked() -> None:
    store, mail = FakeStore(), FakeMail()
    mail.backfill_pages = [MailPage((message("m1", sender="info@acme.com"),), None)]
    directory = FakeDirectory(
        RecordDirectory(
            people_by_email={"info@acme.com": (PersonRef("p1", "o1"), PersonRef("p2", "o2"))},
            org_ids_by_domain={},
        )
    )

    report = await make_service(store, mail, directory=directory).run_pass()

    assert (report.linked, report.shared_emails, report.shared_domains) == (0, 1, 0)
    assert store.links == {}


async def test_a_domain_shared_by_two_organizations_is_counted_and_links_no_organization() -> None:
    store, mail = FakeStore(), FakeMail()
    mail.backfill_pages = [MailPage((message("m1", sender="a@shared.com"),), None)]
    directory = FakeDirectory(
        RecordDirectory(people_by_email={}, org_ids_by_domain={"shared.com": ("o1", "o2")})
    )

    report = await make_service(store, mail, directory=directory).run_pass()

    assert (report.linked, report.shared_emails, report.shared_domains) == (0, 0, 1)
    assert store.links == {}


async def test_the_directory_is_not_loaded_when_nothing_needs_linking() -> None:
    store, directory = FakeStore(), FakeDirectory()

    await make_service(store, directory=directory).run_pass()

    assert directory.loads == 0


async def test_an_address_linked_on_one_pass_is_not_resolved_again_on_the_next() -> None:
    store, mail, calendar = FakeStore(), FakeMail(), FakeCalendar()
    mail.backfill_pages = [MailPage((message("m1", sender=SARA),), None)]
    directory = FakeDirectory(
        RecordDirectory(people_by_email={SARA: (PersonRef("p1", "o1"),)}, org_ids_by_domain={})
    )
    service = make_service(store, mail, calendar, directory)
    await service.run_pass()
    mail.change_pages = [MailPage((), None, "h101")]
    calendar.change_pages = [CalendarPage((), None, "sync-2")]

    second = await service.run_pass()

    assert second.linked == 0
    assert directory.loads == 1


async def test_purging_removes_everything_older_than_the_retention_window() -> None:
    store = FakeStore()

    await make_service(store).purge_expired()

    assert store.purged_before == months_before(NOW, 12)
