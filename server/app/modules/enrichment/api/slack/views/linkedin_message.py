"""Renders a LinkedIn scan as the thread reply under the proposal message —
a separate message so the slower scrape never holds up the proposal itself.
"""

from slack_sdk.models.blocks import Block, DividerBlock, SectionBlock

from app.modules.enrichment.domain.linkedin import JobChange, LinkedInPost, LinkedInScan
from app.modules.notifications import sanitize_mrkdwn

_SNIPPET_CHARS = 200
# Slack caps a section's text at 3000 characters.
_SECTION_CHARS = 2900


def _job_change_line(change: JobChange) -> str:
    contact, profile = change.contact, change.profile
    parts: list[str] = []
    if change.title_changed:
        parts.append(
            f"title {sanitize_mrkdwn(contact.job_title or '?')} → "
            f"*{sanitize_mrkdwn(profile.current_title or '?')}*"
        )
    if change.company_changed:
        parts.append(
            f"company {sanitize_mrkdwn(contact.company_name)} → "
            f"*{sanitize_mrkdwn(profile.current_company or '?')}*"
        )
    return (
        f"• *{sanitize_mrkdwn(contact.name)}* — {'; '.join(parts)} (<{change.source_url}|profile>)"
    )


def _post_line(post: LinkedInPost) -> str:
    snippet = " ".join(post.text.split())[:_SNIPPET_CHARS]
    author = sanitize_mrkdwn(post.author_name or "Unknown")
    when = f" · {post.posted_at:%Y-%m-%d}" if post.posted_at else ""
    return f"• _{author}_{when} — {sanitize_mrkdwn(snippet)} (<{post.url}|view>)"


def _section(title: str, lines: list[str]) -> SectionBlock:
    text = f"*{title}*\n" + "\n".join(lines)
    return SectionBlock(text=text[:_SECTION_CHARS])


def build_linkedin_blocks(scan: LinkedInScan, org_name: str) -> list[Block]:
    blocks: list[Block] = [
        SectionBlock(text=f"*LinkedIn activity for {sanitize_mrkdwn(org_name)}*"),
        DividerBlock(),
    ]
    if scan.job_changes:
        blocks.append(_section("Job changes", [_job_change_line(c) for c in scan.job_changes]))
    if scan.posts:
        blocks.append(_section("Posts in the last month", [_post_line(p) for p in scan.posts]))
    if scan.contacts_without_linkedin:
        names = ", ".join(sanitize_mrkdwn(c.name) for c in scan.contacts_without_linkedin)
        blocks.append(SectionBlock(text=f"_No LinkedIn URL on file, not scraped:_ {names}"))
    return blocks
