import pytest

from app.modules.interactions.application.auto_create import AutoCreateConfig, AutoCreateService
from app.modules.interactions.application.ports.attio_writer import WritesNotAllowedError
from app.modules.interactions.application.ports.auto_create import Candidate, CreatedKind
from app.modules.interactions.domain.auto_create import (
    FREE_EMAIL_DOMAINS,
    organization_name,
    person_name,
    registrable_domain,
)
from app.modules.interactions.domain.linking import PersonRef, RecordDirectory

INTERNAL = ("wusoolcapital.com", "dopaminecap.com")


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        ("Sara Lee", "Sara Lee"),
        ("  Sara Lee ", "Sara Lee"),
        (None, "Sara"),
        ("", "Sara"),
        ("Sara@Acme.com", "Sara"),
        ("CEO ceo@bigcorp.com", "Sara"),
        ("Sara\x00Lee", "Sara"),
        ("x" * 101, "Sara"),
        ("Sara\n  Lee", "Sara Lee"),
    ],
)
def test_person_name_uses_a_sensible_display_name_else_builds_one(
    display: str | None, expected: str
) -> None:
    assert person_name(display, "sara@acme.com") == expected


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("sinan@lokam.ai", "Sinan"),
        ("abhishek.bajaj@nyu.edu", "Abhishek Bajaj"),
        ("mary_jane-smith@acme.com", "Mary Jane Smith"),
        ("THAHA@capella.ae", "Thaha"),
        ("admin@raizn.net", "admin@raizn.net"),
        ("info@acme.com", "info@acme.com"),
        ("jsmith42@acme.com", "jsmith42@acme.com"),
        ("a1.b@acme.com", "a1.b@acme.com"),
        ("..@acme.com", "..@acme.com"),
    ],
)
def test_without_a_display_name_the_name_comes_from_the_address(email: str, expected: str) -> None:
    assert person_name(None, email) == expected


@pytest.mark.parametrize(
    ("domain", "registrable", "name"),
    [
        ("acme.com", "acme.com", "Acme"),
        ("mail.acme.com", "acme.com", "Acme"),
        ("www.acme-digital.com", "acme-digital.com", "Acme Digital"),
        ("acme.co.uk", "acme.co.uk", "Acme"),
        ("mail.acme.co.uk", "acme.co.uk", "Acme"),
    ],
)
def test_organization_name_and_domain_come_from_the_company_domain(
    domain: str, registrable: str, name: str
) -> None:
    assert registrable_domain(domain) == registrable
    assert organization_name(domain) == name


def test_the_free_email_list_extends_the_benchmark_one() -> None:
    assert {"gmail.com", "proton.me"} <= FREE_EMAIL_DOMAINS


def _candidate(
    email: str = "sara@acme.com",
    *,
    name: str | None = "Sara Lee",
    two_way: bool = True,
    meeting: bool = False,
) -> Candidate:
    return Candidate(email, email.split("@")[1], name, two_way, meeting)


class _Source:
    def __init__(self, *candidates: Candidate) -> None:
        self.candidates_ = candidates

    async def candidates(self, internal_domains: tuple[str, ...]) -> tuple[Candidate, ...]:
        return self.candidates_


class _Directory:
    def __init__(self, directory: RecordDirectory | None = None) -> None:
        self.directory = directory or RecordDirectory({}, {})

    async def load(self) -> RecordDirectory:
        return self.directory


class _Keys:
    def __init__(self) -> None:
        self.saved: dict[tuple[CreatedKind, str], str] = {}

    async def get(self, kind: CreatedKind, key: str) -> str | None:
        return self.saved.get((kind, key))

    async def save(self, kind: CreatedKind, key: str, record_id: str) -> None:
        self.saved[(kind, key)] = record_id


class _Creator:
    def __init__(
        self,
        existing: frozenset[str] = frozenset(),
        fail_person_for: str | None = None,
        refuse: bool = False,
    ) -> None:
        self.existing = existing
        self.fail_person_for = fail_person_for
        self.refuse = refuse
        self.orgs: list[tuple[str, str]] = []
        self.people: list[tuple[str, str, str | None]] = []

    async def person_exists(self, email: str) -> bool:
        return email in self.existing

    async def create_organization(self, name: str, domain: str) -> str:
        if self.refuse:
            raise WritesNotAllowedError("test instance")
        self.orgs.append((name, domain))
        return f"org-{len(self.orgs)}"

    async def create_person(self, name: str, email: str, organization_id: str | None) -> str:
        if self.refuse:
            raise WritesNotAllowedError("test instance")
        if email == self.fail_person_for:
            raise RuntimeError("attio said no")
        self.people.append((name, email, organization_id))
        return f"person-{len(self.people)}"


def _service(
    creator: _Creator,
    *candidates: Candidate,
    directory: RecordDirectory | None = None,
    cap: int = 20,
    dry_run: bool = False,
    keys: _Keys | None = None,
) -> AutoCreateService:
    config = AutoCreateConfig(INTERNAL, FREE_EMAIL_DOMAINS, cap, dry_run)
    return AutoCreateService(
        _Source(*candidates), _Directory(directory), creator, keys or _Keys(), config
    )


async def test_a_new_contact_at_a_new_company_creates_the_organization_then_the_person() -> None:
    creator = _Creator()

    report = await _service(creator, _candidate()).run_round()

    assert creator.orgs == [("Acme", "acme.com")]
    assert creator.people == [("Sara Lee", "sara@acme.com", "org-1")]
    assert (report.created_people, report.created_orgs, report.failed) == (1, 1, 0)


async def test_a_company_already_in_the_crm_gets_only_the_person() -> None:
    creator = _Creator()
    directory = RecordDirectory({}, {"acme.com": ("org-9",)})

    report = await _service(creator, _candidate(), directory=directory).run_round()

    assert creator.orgs == []
    assert creator.people == [("Sara Lee", "sara@acme.com", "org-9")]
    assert (report.created_people, report.created_orgs) == (1, 0)


async def test_two_contacts_at_one_new_company_share_one_organization() -> None:
    creator = _Creator()

    await _service(creator, _candidate(), _candidate("tom@acme.com", name=None)).run_round()

    assert len(creator.orgs) == 1
    assert [org for _, _, org in creator.people] == ["org-1", "org-1"]
    assert creator.people[1][0] == "Tom"


async def test_a_person_attio_already_has_is_left_for_the_next_pass_to_link() -> None:
    creator = _Creator(existing=frozenset({"sara@acme.com"}))

    report = await _service(creator, _candidate()).run_round()

    assert (creator.orgs, creator.people) == ([], [])
    assert report.existing == 1


async def test_a_person_the_directory_already_knows_is_not_created_again() -> None:
    creator = _Creator()
    directory = RecordDirectory({"sara@acme.com": (PersonRef("p1", None),)}, {})

    report = await _service(creator, _candidate(), directory=directory).run_round()

    assert (creator.orgs, creator.people, report.existing) == ([], [], 1)


@pytest.mark.parametrize(
    "candidate",
    [
        _candidate(two_way=False),
        _candidate("someone@gmail.com"),
        _candidate("hugo@wusoolcapital.com"),
        _candidate("noreply@acme.com"),
    ],
)
async def test_candidates_that_fail_the_filter_create_nothing(candidate: Candidate) -> None:
    creator = _Creator()

    report = await _service(creator, candidate).run_round()

    assert (creator.orgs, creator.people, report.skipped) == ([], [], 1)


async def test_an_attended_meeting_alone_is_enough() -> None:
    creator = _Creator()

    await _service(creator, _candidate(two_way=False, meeting=True)).run_round()

    assert len(creator.people) == 1


async def test_a_domain_shared_by_several_organizations_creates_nothing() -> None:
    creator = _Creator()
    directory = RecordDirectory({}, {"acme.com": ("org-1", "org-2")})

    report = await _service(creator, _candidate(), directory=directory).run_round()

    assert (creator.orgs, creator.people, report.shared) == ([], [], 1)


async def test_a_dry_run_counts_what_it_would_create_and_creates_nothing() -> None:
    creator = _Creator()

    report = await _service(
        creator, _candidate(), _candidate("tom@acme.com"), dry_run=True
    ).run_round()

    assert (creator.orgs, creator.people) == ([], [])
    assert (report.created_people, report.created_orgs, report.dry_run) == (2, 1, True)


async def test_the_round_stops_at_the_cap_and_says_so() -> None:
    creator = _Creator()

    report = await _service(
        creator,
        _candidate("a@one.com"),
        _candidate("b@two.com"),
        _candidate("c@three.com"),
        cap=2,
    ).run_round()

    assert (report.created_people, report.hit_cap) == (2, True)


async def test_one_failing_address_does_not_stop_the_rest() -> None:
    creator = _Creator(fail_person_for="a@one.com")

    report = await _service(creator, _candidate("a@one.com"), _candidate("b@two.com")).run_round()

    assert [email for _, email, _ in creator.people] == ["b@two.com"]
    assert (report.created_people, report.failed) == (1, 1)


async def test_an_organization_made_before_a_person_failed_is_reused_next_round() -> None:
    creator = _Creator(fail_person_for="a@one.com")
    service = _service(creator, _candidate("a@one.com"))
    await service.run_round()
    creator.fail_person_for = None

    await service.run_round()

    assert len(creator.orgs) == 1
    assert creator.people == [("Sara Lee", "a@one.com", "org-1")]


async def test_a_refusal_to_write_stops_the_whole_round() -> None:
    with pytest.raises(WritesNotAllowedError):
        await _service(_Creator(refuse=True), _candidate()).run_round()


async def test_each_create_is_recorded_in_the_keys_table() -> None:
    keys = _Keys()

    await _service(_Creator(), _candidate(), keys=keys).run_round()

    assert keys.saved == {
        (CreatedKind.ORGANIZATION, "acme.com"): "org-1",
        (CreatedKind.PERSON, "sara@acme.com"): "person-1",
    }


async def test_after_a_restart_the_recorded_organization_is_reused_not_made_again() -> None:
    keys = _Keys()
    first = _Creator(fail_person_for="a@one.com")
    await _service(first, _candidate("a@one.com"), keys=keys).run_round()
    second = _Creator()

    # A new service and a new creator: nothing is remembered but the keys table.
    await _service(second, _candidate("a@one.com"), keys=keys).run_round()

    assert second.orgs == []
    assert second.people == [("Sara Lee", "a@one.com", "org-1")]


async def test_a_person_already_recorded_is_never_created_again() -> None:
    keys = _Keys()
    keys.saved[(CreatedKind.PERSON, "sara@acme.com")] = "person-9"
    creator = _Creator()

    report = await _service(creator, _candidate(), keys=keys).run_round()

    assert (creator.orgs, creator.people, report.existing) == ([], [], 1)


async def test_an_address_that_keeps_failing_stops_using_the_rounds_cap() -> None:
    creator = _Creator(fail_person_for="a@one.com")
    service = _service(creator, _candidate("a@one.com"), _candidate("b@two.com"), cap=1)

    reports = [await service.run_round() for _ in range(5)]

    # It fails three times and then waits for a restart; the next address is then served.
    assert [r.failed for r in reports] == [1, 1, 1, 0, 0]
    assert [email for _, email, _ in creator.people] == ["b@two.com"]
