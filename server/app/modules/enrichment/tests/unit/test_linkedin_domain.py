import pytest

from app.modules.enrichment.domain.linkedin import (
    Contact,
    LinkedInProfile,
    detect_job_change,
    profile_key,
)


def _contact(job_title: str | None = "CFO", company: str = "Acme Co") -> Contact:
    return Contact(
        person_attio_id="p1",
        name="Jane Doe",
        company_name=company,
        linkedin_url="https://www.linkedin.com/in/jane-doe",
        job_title=job_title,
    )


def _profile(title: str | None, company: str | None) -> LinkedInProfile:
    return LinkedInProfile(
        url="https://www.linkedin.com/in/jane-doe", current_title=title, current_company=company
    )


def test_new_employer_is_a_company_change() -> None:
    change = detect_job_change(_contact(), _profile("CFO", "Globex"))

    assert change is not None
    assert change.company_changed
    assert not change.title_changed
    assert change.source_url == "https://www.linkedin.com/in/jane-doe"


def test_new_title_at_same_employer_is_a_title_change() -> None:
    change = detect_job_change(_contact(), _profile("CEO", "Acme Co"))

    assert change is not None
    assert change.title_changed
    assert not change.company_changed


@pytest.mark.parametrize(
    ("title", "company"),
    [
        ("cfo", "ACME CO"),
        ("C.F.O.", "Acme Co."),
        ("  CFO  ", "Acme   Co"),
        ("CFO & Co-Founder", "Acme Co Holdings"),
    ],
)
def test_trivial_wording_differences_are_not_a_change(title: str, company: str) -> None:
    assert detect_job_change(_contact(), _profile(title, company)) is None


@pytest.mark.parametrize("job_title", [None, ""])
def test_missing_crm_title_means_unknown_not_changed(job_title: str | None) -> None:
    assert detect_job_change(_contact(job_title=job_title), _profile("CEO", "Acme Co")) is None


def test_missing_scraped_values_are_not_a_change() -> None:
    assert detect_job_change(_contact(), _profile(None, None)) is None


def test_punctuation_only_value_is_not_a_change() -> None:
    assert detect_job_change(_contact(), _profile("--", "Acme Co")) is None


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/in/Jane-Doe/",
        "http://linkedin.com/in/jane-doe?trk=x",
        "linkedin.com/in/jane-doe",
    ],
)
def test_profile_key_ignores_scheme_case_and_trailing_parts(url: str) -> None:
    assert profile_key(url) == "jane-doe"


def test_profile_key_is_none_for_a_non_profile_url() -> None:
    assert profile_key("https://www.linkedin.com/company/acme") is None
    assert profile_key(None) is None
