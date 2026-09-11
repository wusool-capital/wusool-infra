"""Composition roots for Slack handlers — glue code: constructs
sessions/repositories/services and calls application-layer commands.

`_review_port_holder` is registered once at process startup by
`server/main.py` (the composition root that already imports both this
module and `ddl_commands`) via `configure_review_port` — `enrichment`
itself never imports `ddl_commands`, so it cannot build its own adapter;
see `enrichment/__init__.py`'s docstring.
"""

import logging
import uuid
from functools import lru_cache

from app.modules.enrichment.application.ports.company_data import CompanyDataClient
from app.modules.enrichment.application.ports.review import EnrichmentReviewPort
from app.modules.enrichment.application.service import EnrichmentService
from app.modules.enrichment.bootstrap import (
    build_bedrock_client,
    build_diffbot_client,
    build_enrichment_service,
    build_people_data_labs_client,
    build_research_client,
)
from app.modules.enrichment.bootstrap import build_slack_notifier as _build_slack_notifier
from app.modules.enrichment.config import get_settings
from app.modules.enrichment.domain.targets import (
    EnrichmentTarget,
    EnrichmentTargetKind,
    ResolvedOrgRole,
)
from app.modules.enrichment.persistence.database import get_sessionmaker
from app.modules.enrichment.persistence.role_lookup import SqlAlchemyRoleReader
from app.modules.enrichment.providers.bedrock.client import BedrockConverseClient
from app.modules.enrichment.providers.diffbot.client import DiffbotCompanyDataClient
from app.modules.enrichment.providers.firecrawl.client import FirecrawlResearchClient
from app.modules.enrichment.providers.people_data_labs.client import (
    PeopleDataLabsCompanyDataClient,
)
from app.modules.notifications import SlackWebClientNotifier
from app.modules.organizations import OrganizationRepository

logger = logging.getLogger(__name__)

_review_port_holder: EnrichmentReviewPort | None = None


def configure_review_port(port: EnrichmentReviewPort) -> None:
    global _review_port_holder
    _review_port_holder = port


def _review_port() -> EnrichmentReviewPort:
    if _review_port_holder is None:
        raise RuntimeError(
            "enrichment review port not configured — call configure_review_port() at startup"
        )
    return _review_port_holder


@lru_cache
def _bedrock_client() -> BedrockConverseClient:
    return build_bedrock_client()


@lru_cache
def _research_client() -> FirecrawlResearchClient | None:
    api_key = get_settings().firecrawl_api_key
    if not api_key:
        logger.warning(
            "firecrawl_api_key_unset — enrichment research is disabled; "
            "set FIRECRAWL_API_KEY to enable it"
        )
        return None
    return build_research_client(api_key)


@lru_cache
def _diffbot_client() -> DiffbotCompanyDataClient | None:
    api_key = get_settings().diffbot_api_key
    if not api_key:
        logger.warning("diffbot_api_key_unset — this tier of seller enrichment is disabled")
        return None
    return build_diffbot_client(api_key)


@lru_cache
def _people_data_labs_client() -> PeopleDataLabsCompanyDataClient | None:
    api_key = get_settings().people_data_labs_api_key
    if not api_key:
        logger.warning(
            "people_data_labs_api_key_unset — this tier of seller enrichment is disabled"
        )
        return None
    return build_people_data_labs_client(api_key)


def _company_data_clients() -> tuple[CompanyDataClient, ...]:
    # Order matters: Diffbot's free tier is far larger (10k/mo vs. PDL's
    # 100/mo), so it's tried first and PDL only fills whatever it misses.
    return tuple(c for c in (_diffbot_client(), _people_data_labs_client()) if c is not None)


def enrichment_service() -> EnrichmentService:
    return build_enrichment_service(
        sessionmaker=get_sessionmaker(),
        bedrock_client=_bedrock_client(),
        research_client=_research_client(),
        review_port=_review_port(),
        company_data_clients=_company_data_clients(),
    )


def slack_notifier() -> SlackWebClientNotifier:
    return _build_slack_notifier()


async def resolve_org_roles(org_name: str) -> list[ResolvedOrgRole]:
    """Every active seller/buyer role on any organization fuzzy-matching
    `org_name`, both kinds — `/enrich-seller`/`/enrich-buyer` each filter
    this down to their own kind afterward, so this stays kind-agnostic
    rather than taking a `kind` filter itself.
    """
    async with get_sessionmaker()() as session:
        candidates = await OrganizationRepository(session).search_by_name(org_name)

    resolved: list[ResolvedOrgRole] = []
    for org in candidates:
        for role in org.seller_roles:
            if role.is_active:
                resolved.append(
                    ResolvedOrgRole(
                        org_attio_id=org.attio_id,
                        org_name=org.name,
                        role_id=str(role.id),
                        kind="seller",
                    )
                )
        for role in org.buyer_roles:
            if role.is_active:
                resolved.append(
                    ResolvedOrgRole(
                        org_attio_id=org.attio_id,
                        org_name=org.name,
                        role_id=str(role.id),
                        kind="buyer",
                    )
                )
    return resolved


def target_from_resolved(resolved: ResolvedOrgRole) -> EnrichmentTarget:
    return EnrichmentTarget(
        kind=EnrichmentTargetKind(resolved.kind),
        role_id=uuid.UUID(resolved.role_id),
        org_attio_id=resolved.org_attio_id,
        org_name=resolved.org_name,
    )


async def resolve_target(*, kind: str, role_id: uuid.UUID) -> EnrichmentTarget | None:
    """Resolves a target from just a role id/kind — for a caller (a Slack
    button) that doesn't already have `org_attio_id`/`org_name` in hand.
    """
    reader = SqlAlchemyRoleReader(get_sessionmaker())
    return await reader.resolve_target(kind=EnrichmentTargetKind(kind), role_id=role_id)


async def propose_and_post(target: EnrichmentTarget, *, channel_id: str) -> None:
    """Background-task body — research + LLM extraction routinely runs
    past Slack's 3s ack budget, so this posts a placeholder immediately and
    updates it once the proposal is ready, the same pattern
    `matching_engine.run_match_and_post` uses for `/find-match`.
    """
    from app.modules.enrichment.api.slack.views.proposal_message import build_proposal_blocks

    notifier = slack_notifier()
    placeholder_ts = await notifier.post_message(
        channel=channel_id, text=f"🔎 *_Researching {target.org_name}…_*"
    )
    try:
        proposal = await enrichment_service().propose(target)
        await notifier.update_message(
            channel=channel_id,
            ts=placeholder_ts,
            text=f"Enrichment proposal for {target.org_name}",
            blocks=build_proposal_blocks(proposal),
        )
    except Exception:
        logger.exception("enrichment_propose_failed", extra={"org_name": target.org_name})
        await notifier.update_message(
            channel=channel_id, ts=placeholder_ts, text="Enrichment failed unexpectedly."
        )
