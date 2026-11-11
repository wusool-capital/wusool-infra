from app.modules.interactions.domain.calibration import (
    Bucket,
    CompanyInput,
    calibrate,
    parse_label,
)
from app.modules.interactions.domain.linking import RecordDirectory
from app.modules.interactions.domain.model import StrengthLabel as L

INTERNAL = ("wusoolcapital.com", "dopaminecap.com")
READ = frozenset({"jules@wusoolcapital.com", "ramzy@wusoolcapital.com"})
DIRECTORY = RecordDirectory(
    people_by_email={},
    org_ids_by_domain={
        "acme.com": ("o-acme",),
        "beta.io": ("o-beta",),
        "twin.com": ("o-t1", "o-t2"),
        "gamma.co": ("o-gamma",),
        "gamma.org": ("o-gamma",),
    },
)


def _company(
    record: str,
    domain: str,
    label: L | None = L.STRONG,
    user: str | None = "jules@dopaminecap.com",
) -> CompanyInput:
    return CompanyInput(record, (domain,), label, user)


def _run(companies: list[CompanyInput], ours: dict[str, L | None]):
    return calibrate(companies, DIRECTORY, ours, READ, INTERNAL)


def test_exact_and_within_one_are_counted_and_the_matrix_rows_are_attios_label() -> None:
    report = _run(
        [
            _company("c1", "acme.com", L.STRONG),
            _company("c2", "beta.io", L.WEAK),
            _company("c3", "gamma.co", L.VERY_WEAK),
        ],
        {"o-acme": L.STRONG, "o-beta": L.GOOD, "o-gamma": L.STRONG},
    )

    assert (report.compared, report.exact, report.within_one) == (3, 1, 2)
    assert report.matrix[3][3] == 1
    assert report.matrix[1][2] == 1
    assert report.matrix[0][3] == 1
    assert report.mismatch_ids == ("c2", "c3")
    assert not report.passes_gate


def test_a_clean_run_passes_the_gate() -> None:
    report = _run([_company("c1", "acme.com")], {"o-acme": L.STRONG})

    assert (report.exact_rate, report.within_one_rate) == (1.0, 1.0)
    assert report.passes_gate


def test_nothing_compared_means_no_rate_and_no_pass() -> None:
    report = _run([], {})

    assert (report.exact_rate, report.passes_gate) == (None, False)


def test_every_excluded_case_lands_in_its_own_bucket() -> None:
    report = _run(
        [
            _company("no-label", "acme.com", label=None),
            _company("tech", "acme.com", user="tech@wusoolcapital.com"),
            _company("hugo", "acme.com", user="hugo@dopaminecap.com"),
            _company("nobody", "acme.com", user=None),
            _company("lost", "unknown.net"),
            _company("shared", "twin.com"),
            _company("silent", "beta.io"),
        ],
        {"o-acme": L.STRONG, "o-beta": None},
    )

    assert report.compared == 0
    assert report.excluded == {
        Bucket.NO_ATTIO_LABEL: 1,
        Bucket.TECH_USER: 1,
        Bucket.UNREAD_MAILBOX: 2,
        Bucket.NO_ORGANIZATION: 1,
        Bucket.AMBIGUOUS: 1,
        Bucket.NO_TOUCHES: 1,
    }


def test_two_companies_pointing_at_one_organization_are_both_ambiguous() -> None:
    report = _run([_company("c1", "gamma.co"), _company("c2", "gamma.org")], {"o-gamma": L.STRONG})

    assert (report.compared, report.excluded) == (0, {Bucket.AMBIGUOUS: 2})


def test_a_company_whose_domains_reach_two_organizations_is_ambiguous() -> None:
    company = CompanyInput("c1", ("acme.com", "beta.io"), L.STRONG, "jules@wusoolcapital.com")

    report = _run([company], {"o-acme": L.STRONG, "o-beta": L.STRONG})

    assert report.excluded == {Bucket.AMBIGUOUS: 1}


def test_the_alias_domain_of_a_read_mailbox_counts_as_read() -> None:
    report = _run([_company("c1", "acme.com", user="ramzy@dopaminecap.com")], {"o-acme": L.STRONG})

    assert report.compared == 1


def test_a_www_prefix_and_a_subdomain_still_match() -> None:
    report = _run(
        [_company("c1", "www.acme.com"), _company("c2", "mail.beta.io")],
        {"o-acme": L.STRONG, "o-beta": L.STRONG},
    )

    assert report.compared == 2


def test_an_unknown_attio_label_reads_as_no_label() -> None:
    assert parse_label("Medium") is None
    assert parse_label(None) is None
    assert parse_label("Very strong") is L.VERY_STRONG
