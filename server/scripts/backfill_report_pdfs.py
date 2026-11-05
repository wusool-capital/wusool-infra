"""One-off: prints and attaches a PDF to every published report that has none.

Reports flattened before PDFs were printed at publish have no `renderedPdf`, so
their download answers 503 until this runs. It re-syncs each published report,
which prints only the ones missing a PDF; reports with one are left alone. The
sync also rewrites each report's Webflow card, which is idempotent, and flattens
again any report whose source or renderer version changed. A failed report is
listed at the end and the rest still run.

Chromium runs on this machine, not the toolkit server, so the large render
never touches production. Needs `aws sso login` (the Sanity and Webflow secrets
come from Secrets Manager) and `uv run playwright install --only-shell chromium`.

Usage: uv run python scripts/backfill_report_pdfs.py
"""

import asyncio
import logging

import httpx
from pydantic import BaseModel

from app.modules.lead_magnets.bootstrap import build_report_source, build_report_sync
from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.providers.sanity.report_source import API_VERSION

# Published, already flattened; a draft's id starts with "drafts.".
_PUBLISHED_SLUGS = (
    '*[_type == "report" && defined(renderedHtml) && !(_id in path("drafts.**"))].slug.current'
)


class _Slugs(BaseModel):
    result: list[str]


async def _published_slugs(project_id: str, dataset: str) -> list[str]:
    url = f"https://{project_id}.api.sanity.io/{API_VERSION}/data/query/{dataset}"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params={"query": _PUBLISHED_SLUGS})
    response.raise_for_status()
    return _Slugs.model_validate_json(response.content).result


async def main() -> None:
    settings = get_settings()
    slugs = await _published_slugs(
        settings.lead_magnet_sanity_project_id, settings.lead_magnet_sanity_dataset
    )
    sync, source = build_report_sync(), build_report_source()
    failed: list[str] = []
    for slug in slugs:
        try:
            await sync.sync(slug=slug, previous_slug=None)
            report = await source.refresh(slug)
        except Exception:  # noqa: BLE001 - one bad report must not stop the rest
            logging.exception("backfill_failed slug=%s", slug)
            report = None
        pdf_url = report.pdf_url if report else None
        print(f"{slug}: {pdf_url or 'NO PDF - see the log above'}")
        if not pdf_url:
            failed.append(slug)
    if failed:
        raise SystemExit(f"{len(failed)} report(s) have no PDF: {', '.join(failed)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
