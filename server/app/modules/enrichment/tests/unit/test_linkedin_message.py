from datetime import datetime

from slack_sdk.models.blocks import SectionBlock

from app.modules.enrichment.api.slack.views.linkedin_message import build_linkedin_blocks
from app.modules.enrichment.domain.linkedin import (
    Contact,
    JobChange,
    LinkedInPost,
    LinkedInProfile,
    LinkedInScan,
    ScanOutcome,
)


def _texts(scan: LinkedInScan) -> str:
    return "\n".join(
        b.text.text for b in build_linkedin_blocks(scan, "Acme Co") if isinstance(b, SectionBlock)
    )


def test_renders_job_change_post_and_missing_contacts() -> None:
    contact = Contact("p1", "Jane Doe", "Acme Co", "https://linkedin.com/in/jane", "CFO")
    scan = LinkedInScan(
        job_changes=(
            JobChange(
                contact=contact,
                profile=LinkedInProfile(
                    url="https://linkedin.com/in/jane",
                    current_title="CFO",
                    current_company="Globex",
                ),
                title_changed=False,
                company_changed=True,
                source_url="https://linkedin.com/in/jane",
            ),
        ),
        posts=(
            LinkedInPost(
                external_id="1",
                url="https://linkedin.com/posts/1",
                text="We closed an acquisition",
                author_name="Jane Doe",
                posted_at=datetime(2026, 10, 9),
            ),
        ),
        contacts_without_linkedin=(Contact("p2", "Omar Ali", "Acme Co"),),
    )

    text = _texts(scan)

    assert "Jane Doe" in text and "Globex" in text
    assert "We closed an acquisition" in text and "2026-10-09" in text
    assert "Omar Ali" in text


def test_long_post_is_truncated_to_fit_a_slack_section() -> None:
    posts = tuple(
        LinkedInPost(external_id=str(i), url=f"https://linkedin.com/posts/{i}", text="x" * 5000)
        for i in range(10)
    )

    for block in build_linkedin_blocks(LinkedInScan(posts=posts), "Acme Co"):
        if isinstance(block, SectionBlock):
            assert len(block.text.text) <= 3000


def test_a_long_section_drops_whole_lines_and_never_cuts_a_link() -> None:
    posts = tuple(
        LinkedInPost(
            external_id=str(i),
            url="https://www.linkedin.com/posts/" + "x" * 300 + str(i),
            text="y" * 400,
            author_name="Jane Doe",
        )
        for i in range(10)
    )

    blocks = [b for b in build_linkedin_blocks(LinkedInScan(posts=posts), "Acme Co")]
    text = next(b.text.text for b in blocks if "Posts from the past month" in str(b.to_dict()))

    assert len(text) <= 3000
    assert text.count("<") == text.count(">")
    assert "…and" in text and "more_" in text


def test_a_completed_scan_with_nothing_new_says_so() -> None:
    assert "No new posts in the past month" in _texts(LinkedInScan())


def test_a_skipped_scan_names_the_missing_linkedin_page() -> None:
    text = _texts(LinkedInScan(outcome=ScanOutcome.SKIPPED))

    assert "no LinkedIn page is saved for Acme Co" in text
    assert "No new posts" not in text


def test_a_failed_scan_says_so_without_detail() -> None:
    text = _texts(LinkedInScan(outcome=ScanOutcome.FAILED))

    assert "scan failed" in text and "Try again later" in text
