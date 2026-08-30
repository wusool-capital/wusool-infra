"""Fetches one Attio record/entry and upserts it into the matching Postgres
table — the same field mapping and `ON CONFLICT` SQL already proven in
`database/sync-postgres.ps1`, scoped to a single row instead of a full
page-through. Every statement here is idempotent: re-running it with the
same current Attio state, any number of times, from any order of events, is
always safe.

Foreign keys that reference a row which may not have been synced yet
(`owner_attio_id` -> users, `company_attio_id` -> organizations, etc.) are
guarded with `CASE WHEN EXISTS (...)` so a webhook arriving slightly out of
order degrades to a NULL reference instead of failing the whole upsert —
`sync-postgres.ps1`'s own periodic full resync (or the next event touching
the same row) fills it in once the referenced row exists. The one exception
is `buyer_roles`/`seller_roles`' own `org_attio_id`: that one can't be
nulled out (it's the row's own key), so a buyer/seller-role event that
arrives before its organization has synced is expected to fail loudly, get
caught by the background-task handler (see `router.py`), and resolve itself
on the next event or the nightly full resync.

`organizations` and `person` both have a deletion story (`removed_at`,
matching the convention `sync-postgres.ps1` already established for both —
`person` needs it too since `buyer_roles.key_contact_attio_id`/
`deals.buyer_person_attio_id` reference it with `ON DELETE NO ACTION`).
`record.deleted`/`list-entry.deleted` for every other table is deliberately
out of scope here, because the existing bulk script doesn't prune those
tables either. Closing that gap is a separate, pre-existing piece of work,
not a regression this sync introduces.
"""

import json
import logging

from sqlalchemy import text

from ddl_commands.modules.attio_sync import values as v
from ddl_commands.modules.attio_sync.retry import get_with_retry, patch_with_retry, post_with_retry
from ddl_commands.shared.attio.client import AttioClient
from ddl_commands.shared.database.session import get_sessionmaker

_logger = logging.getLogger("ddl_commands.attio_sync")


def _j(value):
    return None if value is None else json.dumps(value)


# ---------------------------------------------------------------------------
# activities — generic change log, one row per real-time sync
# ---------------------------------------------------------------------------
#
# `activities` otherwise holds curated business-interaction rows (calls,
# emails, seller-outreach attempts) from the one-off `backfill-activities.ps1`
# historical import. This adds a second, mechanical kind of row alongside
# those: "this record was created/updated", with no channel/outcome/actor to
# fill in (the webhook envelope carries only ids, never who made the change).
# subject_uuid (not subject_attio_id) is used for buyer_role/seller_role,
# matching backfill-activities.ps1's existing convention for those two
# UUID-keyed tables.

_ACTIVITY_INSERT = text(
    """
    INSERT INTO activities(subject_type, subject_attio_id, subject_uuid, source)
    VALUES (:subject_type, :subject_attio_id, :subject_uuid, :source)
    """
)


async def _log_activity(
    session,
    subject_type: str,
    *,
    subject_attio_id: str | None = None,
    subject_uuid: str | None = None,
    source: str = "attio_webhook",
) -> None:
    await session.execute(
        _ACTIVITY_INSERT,
        {
            "subject_type": subject_type,
            "subject_attio_id": subject_attio_id,
            "subject_uuid": subject_uuid,
            "source": source,
        },
    )


# ---------------------------------------------------------------------------
# users (workspace members) -- full-refresh only, no real-time event
# ---------------------------------------------------------------------------
#
# Attio does fire workspace-member.* webhook events, but they're not routed
# anywhere by dispatch.py: workspace members aren't a generic Attio object
# (no object_id, not reachable via /objects/...), and there's no
# single-member GET endpoint to re-fetch just one from -- only the bulk
# /workspace_members listing sync-postgres.ps1 already uses. Team membership
# also changes rarely enough that this isn't worth a real-time path. This
# function exists for full_resync.py (the nightly safety net) to call.

_USER_UPSERT = text(
    """
    INSERT INTO users(attio_id, name, email, access, active, raw_attio)
    VALUES (:attio_id, :name, :email, :access, :active, CAST(:raw_attio AS jsonb))
    ON CONFLICT (attio_id) DO UPDATE SET
        name=excluded.name, email=excluded.email, access=excluded.access,
        active=excluded.active, raw_attio=excluded.raw_attio, updated_at=now()
    """
)


async def sync_all_users(client: AttioClient) -> int:
    response = await get_with_retry(client, "/workspace_members")
    members = response.get("data", [])
    count = 0
    async with get_sessionmaker()() as session:
        for m in members:
            mid = str(
                (m.get("id") or {}).get("workspace_member_id")
                or m.get("workspace_member_id")
                or m.get("id")
                or ""
            )
            if not mid:
                continue
            name = (
                m.get("name")
                or " ".join(x for x in (m.get("first_name"), m.get("last_name")) if x)
                or m.get("email_address")
                or mid
            )
            await session.execute(
                _USER_UPSERT,
                {
                    "attio_id": mid,
                    "name": name,
                    "email": m.get("email_address"),
                    "access": m.get("access_level"),
                    "active": not bool(m.get("is_suspended")),
                    "raw_attio": _j(m),
                },
            )
            count += 1
        await session.commit()
    return count


# ---------------------------------------------------------------------------
# organizations
# ---------------------------------------------------------------------------

_ORG_UPSERT = text(
    """
    INSERT INTO organizations(
        attio_id, name, description, type, client_type, sector_focus, stage_focus,
        geographic_focus, hq_country, domains, categories, relationship_status,
        connection_strength, owner_attio_id, last_interaction_at, funding_raised,
        estimated_arr, angellist, facebook, instagram, twitter, twitter_follower_count,
        foundation_date, ticket_size, lead_source, employee_range, linkedin, logo_url, raw_attio
    ) VALUES (
        :attio_id, :name, :description, :type, :client_type, :sector_focus, :stage_focus,
        :geographic_focus, :hq_country, :domains, :categories, :relationship_status,
        :connection_strength,
        CASE WHEN EXISTS (SELECT 1 FROM users WHERE attio_id = :owner_attio_id)
             THEN :owner_attio_id ELSE NULL END,
        :last_interaction_at, CAST(:funding_raised AS jsonb), :estimated_arr,
        :angellist, :facebook, :instagram, :twitter, :twitter_follower_count,
        :foundation_date, :ticket_size, :lead_source, :employee_range, :linkedin, :logo_url,
        CAST(:raw_attio AS jsonb)
    )
    ON CONFLICT (attio_id) DO UPDATE SET
        name=excluded.name, description=excluded.description, type=excluded.type,
        client_type=excluded.client_type, sector_focus=excluded.sector_focus,
        stage_focus=excluded.stage_focus, geographic_focus=excluded.geographic_focus,
        hq_country=excluded.hq_country, domains=excluded.domains,
        categories=excluded.categories, relationship_status=excluded.relationship_status,
        connection_strength=excluded.connection_strength, owner_attio_id=excluded.owner_attio_id,
        last_interaction_at=excluded.last_interaction_at, funding_raised=excluded.funding_raised,
        estimated_arr=excluded.estimated_arr, angellist=excluded.angellist,
        facebook=excluded.facebook, instagram=excluded.instagram, twitter=excluded.twitter,
        twitter_follower_count=excluded.twitter_follower_count,
        foundation_date=excluded.foundation_date, ticket_size=excluded.ticket_size,
        lead_source=excluded.lead_source, employee_range=excluded.employee_range,
        linkedin=excluded.linkedin, logo_url=excluded.logo_url, raw_attio=excluded.raw_attio,
        updated_at=now(), removed_at=NULL
    """
)


async def sync_organization(client: AttioClient, record_id: str) -> None:
    fetched = await get_with_retry(client, f"/objects/organizations/records/{record_id}")
    data = fetched["data"]
    values = v.vals(data)
    rid = v.record_id(data)
    params = {
        "attio_id": rid,
        "name": v.first(values, "name") or f"Unnamed DEV Organization [{rid}]",
        "description": v.first(values, "description"),
        "type": v.titles(values, "type"),
        "client_type": v.first(values, "client_type"),
        "sector_focus": v.titles(values, "sector_focus"),
        "stage_focus": v.titles(values, "stage"),
        "geographic_focus": v.titles(values, "geographic_focus"),
        "hq_country": v.first(values, "hq_country"),
        "domains": v.domains(values),
        "categories": v.titles(values, "categories"),
        "relationship_status": v.first(values, "relationship_status"),
        "connection_strength": v.first(values, "strongest_connection_strength"),
        "owner_attio_id": v.actor(values, "owner"),
        "last_interaction_at": v.timestamp(values, "last_interaction_at"),
        "funding_raised": _j(v.money(values, "funding_raised")),
        "estimated_arr": v.first(values, "estimated_arr"),
        "raw_attio": _j(data),
    }
    params.update(
        {
            "angellist": v.first(values, "angellist"),
            "facebook": v.first(values, "facebook"),
            "instagram": v.first(values, "instagram"),
            "twitter": v.first(values, "twitter"),
            "twitter_follower_count": v.integer(values, "twitter_follower_count"),
            "foundation_date": v.date(values, "foundation_date"),
            "ticket_size": v.first(values, "ticket_size"),
            "lead_source": v.first(values, "lead_source"),
            "employee_range": v.first(values, "employee_range"),
            "linkedin": v.first(values, "linkedin"),
            "logo_url": v.first(values, "logo_url"),
        }
    )
    async with get_sessionmaker()() as session:
        await session.execute(_ORG_UPSERT, params)
        await _log_activity(session, "Organization", subject_attio_id=rid)
        await session.commit()


async def delete_organization(record_id: str) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(
            text("UPDATE organizations SET removed_at = now() WHERE attio_id = :attio_id"),
            {"attio_id": record_id},
        )
        await session.commit()


# ---------------------------------------------------------------------------
# person
# ---------------------------------------------------------------------------

_PERSON_UPSERT = text(
    """
    INSERT INTO person(
        attio_id, name, role, company_attio_id, email, linkedin, relationship_status,
        connection_strength, owner_attio_id, last_interaction_at, job_title, contact_type,
        phone, avatar_url, angellist, facebook, instagram, twitter, twitter_follower_count,
        raw_attio
    ) VALUES (
        :attio_id, :name, :role,
        CASE WHEN EXISTS (SELECT 1 FROM organizations WHERE attio_id = :company_attio_id)
             THEN :company_attio_id ELSE NULL END,
        :email, :linkedin, :relationship_status, :connection_strength,
        CASE WHEN EXISTS (SELECT 1 FROM users WHERE attio_id = :owner_attio_id)
             THEN :owner_attio_id ELSE NULL END,
        :last_interaction_at, :job_title, :contact_type, :phone, :avatar_url,
        :angellist, :facebook, :instagram, :twitter, :twitter_follower_count,
        CAST(:raw_attio AS jsonb)
    )
    ON CONFLICT (attio_id) DO UPDATE SET
        name=excluded.name, role=excluded.role, company_attio_id=excluded.company_attio_id,
        email=excluded.email, linkedin=excluded.linkedin,
        relationship_status=excluded.relationship_status,
        connection_strength=excluded.connection_strength, owner_attio_id=excluded.owner_attio_id,
        last_interaction_at=excluded.last_interaction_at, job_title=excluded.job_title,
        contact_type=excluded.contact_type, phone=excluded.phone,
        avatar_url=excluded.avatar_url, angellist=excluded.angellist,
        facebook=excluded.facebook, instagram=excluded.instagram, twitter=excluded.twitter,
        twitter_follower_count=excluded.twitter_follower_count,
        raw_attio=excluded.raw_attio, updated_at=now()
    """
)


async def sync_person(client: AttioClient, record_id: str) -> None:
    fetched = await get_with_retry(client, f"/objects/person/records/{record_id}")
    data = fetched["data"]
    values = v.vals(data)
    rid = v.record_id(data)
    roles = v.titles(values, "role") or v.titles(values, "job_title")
    params = {
        "attio_id": rid,
        "name": v.first(values, "name") or f"Unnamed DEV Person [{rid}]",
        "role": ", ".join(roles) or v.first(values, "role"),
        "company_attio_id": v.ref(values, "company"),
        "email": [
            x.get("email_address")
            for x in v.raw_items(values, "email_addresses")
            if x.get("email_address")
        ],
        "linkedin": v.first(values, "linkedin"),
        "relationship_status": v.first(values, "relationship_status"),
        "connection_strength": v.first(values, "strongest_connection_strength"),
        "owner_attio_id": v.actor(values, "owner"),
        "last_interaction_at": v.timestamp(values, "last_interaction_at"),
        "job_title": v.first(values, "job_title"),
        "contact_type": v.first(values, "contact_type"),
        "phone": v.first(values, "phone"),
        "avatar_url": v.first(values, "avatar_url"),
        "angellist": v.first(values, "angellist"),
        "facebook": v.first(values, "facebook"),
        "instagram": v.first(values, "instagram"),
        "twitter": v.first(values, "twitter"),
        "twitter_follower_count": v.integer(values, "twitter_follower_count"),
        "raw_attio": _j(data),
    }
    async with get_sessionmaker()() as session:
        await session.execute(_PERSON_UPSERT, params)
        await _log_activity(session, "Person", subject_attio_id=rid)
        await session.commit()


async def delete_person(record_id: str) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(
            text("UPDATE person SET removed_at = now() WHERE attio_id = :attio_id"),
            {"attio_id": record_id},
        )
        await session.commit()


# ---------------------------------------------------------------------------
# deals
# ---------------------------------------------------------------------------

_DEAL_UPSERT = text(
    """
    INSERT INTO deals(
        attio_id, name, stage, stage_changed_at, buyer_organization_attio_id,
        buyer_person_attio_id, seller_organization_attio_id, owner_attio_id, value,
        teaser_status, nda_count, cim_ready, deal_memo_ready, contract_signed_date,
        exclusivity_date, data_room_substatus, nda_status,
        estimated_deal_value_usd, expected_close_date, fee, assigned_advisor,
        deal_type, universe_constructed, universe_size, shortlist_approved,
        shortlist_size, tier1_contacted, responses, counterparty_interested,
        mandate_start_date, mandate_expiry_date, retainer_amount,
        source_mandate_entry_id, raw_attio
    ) VALUES (
        :attio_id, :name, :stage, :stage_changed_at,
        CASE WHEN EXISTS (SELECT 1 FROM organizations WHERE attio_id = :buyer_id)
             THEN :buyer_id ELSE NULL END,
        CASE WHEN EXISTS (SELECT 1 FROM person WHERE attio_id = :buyer_id)
             THEN :buyer_id ELSE NULL END,
        CASE WHEN EXISTS (SELECT 1 FROM organizations WHERE attio_id = :seller_id)
             THEN :seller_id ELSE NULL END,
        CASE WHEN EXISTS (SELECT 1 FROM users WHERE attio_id = :owner_attio_id)
             THEN :owner_attio_id ELSE NULL END,
        CAST(:value AS jsonb), :teaser_status, :nda_count, :cim_ready, :deal_memo_ready,
        :contract_signed_date, :exclusivity_date, :data_room_substatus,
        :nda_status, :estimated_deal_value_usd, :expected_close_date, :fee,
        :assigned_advisor, :deal_type, COALESCE(:universe_constructed, false),
        :universe_size, COALESCE(:shortlist_approved, false), :shortlist_size,
        :tier1_contacted, :responses, :counterparty_interested,
        :mandate_start_date, :mandate_expiry_date, CAST(:retainer_amount AS jsonb),
        :source_mandate_entry_id, CAST(:raw_attio AS jsonb)
    )
    ON CONFLICT (attio_id) DO UPDATE SET
        name=excluded.name, stage=excluded.stage, stage_changed_at=excluded.stage_changed_at,
        buyer_organization_attio_id=excluded.buyer_organization_attio_id,
        buyer_person_attio_id=excluded.buyer_person_attio_id,
        seller_organization_attio_id=excluded.seller_organization_attio_id,
        owner_attio_id=excluded.owner_attio_id, value=excluded.value,
        teaser_status=excluded.teaser_status, nda_count=excluded.nda_count,
        cim_ready=excluded.cim_ready, deal_memo_ready=excluded.deal_memo_ready,
        contract_signed_date=excluded.contract_signed_date,
        exclusivity_date=excluded.exclusivity_date,
        data_room_substatus=excluded.data_room_substatus, nda_status=excluded.nda_status,
        estimated_deal_value_usd=excluded.estimated_deal_value_usd,
        expected_close_date=excluded.expected_close_date, fee=excluded.fee,
        assigned_advisor=excluded.assigned_advisor, deal_type=excluded.deal_type,
        universe_constructed=excluded.universe_constructed,
        universe_size=excluded.universe_size,
        shortlist_approved=excluded.shortlist_approved,
        shortlist_size=excluded.shortlist_size, tier1_contacted=excluded.tier1_contacted,
        responses=excluded.responses, counterparty_interested=excluded.counterparty_interested,
        mandate_start_date=excluded.mandate_start_date,
        mandate_expiry_date=excluded.mandate_expiry_date,
        retainer_amount=excluded.retainer_amount,
        source_mandate_entry_id=excluded.source_mandate_entry_id,
        raw_attio=excluded.raw_attio,
        updated_at=now()
    """
)


async def sync_deal(client: AttioClient, record_id: str, *, object_slug: str = "deals") -> None:
    """`object_slug` is the actual Attio object api_slug to fetch from —
    "deals" (DEV's native object, the default) or "deal" (SOURCE's custom
    object, singular — see `config.py`'s `attio_deal_object_slug`). Both map
    to the same `deals` Postgres table either way."""
    fetched = await get_with_retry(client, f"/objects/{object_slug}/records/{record_id}")
    data = fetched["data"]
    values = v.vals(data)
    rid = v.record_id(data)
    params = {
        "attio_id": rid,
        "name": v.first(values, "name") or f"Unnamed DEV Deal [{rid}]",
        "stage": v.first(values, "stage"),
        "stage_changed_at": v.timestamp(values, "stage_changed_at"),
        "buyer_id": v.ref(values, "buyer_id"),
        "seller_id": v.ref(values, "seller_id"),
        "owner_attio_id": v.actor(values, "owner"),
        "value": _j(v.money(values, "value") or v.money(values, "deal_value")),
        "teaser_status": v.first(values, "teaser_status"),
        "nda_count": int(v.number(values, "nda_count") or 0),
        "cim_ready": v.boolean(values, "cim_ready"),
        "deal_memo_ready": v.boolean(values, "deal_memo_ready"),
        "contract_signed_date": v.date(values, "contract_signed_date"),
        "exclusivity_date": v.date(values, "exclusivity_date"),
        "data_room_substatus": v.first(values, "data_room_substatus"),
        "nda_status": v.first(values, "nda_status"),
        "estimated_deal_value_usd": v.number(values, "estimated_deal_value_usd"),
        "expected_close_date": v.date(values, "expected_close_date"),
        "fee": v.number(values, "fee"),
        "assigned_advisor": v.titles(values, "assigned_advisor"),
        # Merged in from the retired Mandates list, 2026-08-23 (see
        # migration-decisions.json and the Wusool Schema Handover artifact).
        # Attio slugs stayed start_date/expiry_date -- only the DEV display
        # titles changed to "Mandate Start/Expiry Date", disambiguating them
        # from contract_signed_date/exclusivity_date/expected_close_date
        # above. Postgres columns use the disambiguated name directly.
        "deal_type": v.first(values, "deal_type"),
        "universe_constructed": v.boolean(values, "universe_constructed"),
        "universe_size": v.integer(values, "universe_size"),
        "shortlist_approved": v.boolean(values, "shortlist_approved"),
        "shortlist_size": v.integer(values, "shortlist_size"),
        "tier1_contacted": v.integer(values, "tier1_contacted"),
        "responses": v.integer(values, "responses"),
        "counterparty_interested": v.integer(values, "counterparty_interested"),
        "mandate_start_date": v.date(values, "start_date"),
        "mandate_expiry_date": v.date(values, "expiry_date"),
        "retainer_amount": _j(v.money(values, "retainer_amount")),
        "source_mandate_entry_id": v.first(values, "source_mandate_entry_id"),
        "raw_attio": _j(data),
    }
    async with get_sessionmaker()() as session:
        await session.execute(_DEAL_UPSERT, params)
        await _log_activity(session, "Deal", subject_attio_id=rid)
        await session.commit()


# ---------------------------------------------------------------------------
# buyer_role / seller_role — duplicate-aware via `is_active`
# ---------------------------------------------------------------------------


async def _fetch_siblings(client: AttioClient, list_slug: str, org_id: str) -> list[dict]:
    """Every entry in `list_slug` whose parent is `org_id`. Pages the whole
    list and filters client-side (see `dispatch.py`'s module docstring for
    why — Attio's parent-record filter syntax wasn't confirmed reliable
    enough to bet a write-back on), same technique `sync-postgres.ps1` and
    `crm-sync/scripts/_internal/lists.ps1` already use successfully."""
    siblings: list[dict] = []
    offset = 0
    while True:
        response = await post_with_retry(
            client, f"/lists/{list_slug}/entries/query", {"limit": 500, "offset": offset}
        )
        page = response.get("data", [])
        siblings.extend(e for e in page if v.parent_id(e) == org_id)
        if len(page) < 500:
            return siblings
        offset += 500


async def _reconcile_active_entry(
    client: AttioClient, list_slug: str, org_id: str
) -> tuple[dict, list[dict]]:
    """Ensures exactly one entry for `org_id` in `list_slug` is `is_active`,
    flipping Attio's own flags (not just Postgres's) if needed — `is_active`
    is a real Attio field other consumers read too, so the correction has to
    land there, not just in our mirror. Newest `created_at` wins, the same
    tiebreak `lists.ps1` already applies elsewhere. Returns `(winner, losers)`
    -- every sibling entry for `org_id`, split by which one now holds
    `is_active` -- since `buyer_roles`/`seller_roles.legacy_entry_id` (not
    `org_attio_id`) is the unique key as of the 2026-08-28 migration: every
    DEV entry gets its own Postgres row, not just the active one.
    """
    siblings = await _fetch_siblings(client, list_slug, org_id)
    if not siblings:
        raise ValueError(f"no {list_slug} entries found for org {org_id}")
    siblings.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    winner, *losers = siblings

    if v.boolean(v.vals(winner), "is_active") is not True:
        await patch_with_retry(
            client,
            f"/lists/{list_slug}/entries/{v.entry_id(winner)}",
            {"data": {"entry_values": {"is_active": True}}},
        )
    for loser in losers:
        if v.boolean(v.vals(loser), "is_active") is not False:
            await patch_with_retry(
                client,
                f"/lists/{list_slug}/entries/{v.entry_id(loser)}",
                {"data": {"entry_values": {"is_active": False}}},
            )
    return winner, losers


_BUYER_ROLE_UPSERT = text(
    """
    INSERT INTO buyer_roles(
        org_attio_id, model, mandate_status, ebitda_floor, check_size_min, check_size_max,
        ev_ceiling, deal_structure_tolerance, earnout_tolerance, profitable_only,
        investment_strategy, notes, key_contact_attio_id, acquisition_enrichment,
        deals_introduced, deals_converted, ebitda_ceiling, estimated_aum,
        notable_investments, key_personnel, relationship_warmth, target_geography,
        last_mandate_briefing_date, prior_gcc_acquisition,
        is_active, legacy_entry_id, raw_attio
    ) VALUES (
        :org_attio_id, :model, :mandate_status, CAST(:ebitda_floor AS jsonb),
        CAST(:check_size_min AS jsonb), CAST(:check_size_max AS jsonb),
        CAST(:ev_ceiling AS jsonb), :deal_structure_tolerance, :earnout_tolerance,
        :profitable_only, :investment_strategy, :notes,
        CASE WHEN EXISTS (SELECT 1 FROM person WHERE attio_id = :key_contact_attio_id)
             THEN :key_contact_attio_id ELSE NULL END,
        :acquisition_enrichment, :deals_introduced, :deals_converted,
        CAST(:ebitda_ceiling AS jsonb), CAST(:estimated_aum AS jsonb),
        :notable_investments, :key_personnel, :relationship_warmth, :target_geography,
        :last_mandate_briefing_date, :prior_gcc_acquisition,
        :is_active, :legacy_entry_id, CAST(:raw_attio AS jsonb)
    )
    ON CONFLICT (legacy_entry_id) DO UPDATE SET
        org_attio_id=excluded.org_attio_id,
        model=excluded.model, mandate_status=excluded.mandate_status,
        ebitda_floor=excluded.ebitda_floor, check_size_min=excluded.check_size_min,
        check_size_max=excluded.check_size_max, ev_ceiling=excluded.ev_ceiling,
        deal_structure_tolerance=excluded.deal_structure_tolerance,
        earnout_tolerance=excluded.earnout_tolerance, profitable_only=excluded.profitable_only,
        investment_strategy=excluded.investment_strategy, notes=excluded.notes,
        key_contact_attio_id=excluded.key_contact_attio_id,
        acquisition_enrichment=excluded.acquisition_enrichment,
        deals_introduced=excluded.deals_introduced, deals_converted=excluded.deals_converted,
        ebitda_ceiling=excluded.ebitda_ceiling, estimated_aum=excluded.estimated_aum,
        notable_investments=excluded.notable_investments,
        key_personnel=excluded.key_personnel, relationship_warmth=excluded.relationship_warmth,
        target_geography=excluded.target_geography,
        last_mandate_briefing_date=excluded.last_mandate_briefing_date,
        prior_gcc_acquisition=excluded.prior_gcc_acquisition,
        is_active=excluded.is_active, legacy_entry_id=excluded.legacy_entry_id,
        raw_attio=excluded.raw_attio, updated_at=now()
    RETURNING id
    """
)


async def sync_buyer_role(client: AttioClient, entry_id: str) -> None:
    fetched = await get_with_retry(client, f"/lists/buyer_role/entries/{entry_id}")
    org_id = v.parent_id(fetched["data"])
    winner, losers = await _reconcile_active_entry(client, "buyer_role", org_id)

    async with get_sessionmaker()() as session:
        triggering_row_id = None
        for entry, is_active in [(winner, True)] + [(loser, False) for loser in losers]:
            values = v.vals(entry)
            params = {
                "org_attio_id": org_id,
                "model": v.first(values, "model"),
                "mandate_status": v.first(values, "mandate_status"),
                "ebitda_floor": _j(v.money(values, "ebitda_floor")),
                "check_size_min": _j(v.money(values, "check_size_min")),
                "check_size_max": _j(v.money(values, "check_size_max")),
                "ev_ceiling": _j(v.money(values, "ev_ceiling")),
                "deal_structure_tolerance": v.first(values, "deal_structure_tolerance"),
                "earnout_tolerance": v.boolean(values, "earnout_tolerance"),
                "profitable_only": v.boolean(values, "profitable_only"),
                "investment_strategy": v.first(values, "investment_strategy"),
                "notes": v.first(values, "notes"),
                "key_contact_attio_id": v.ref(values, "key_contact"),
                "acquisition_enrichment": v.first(values, "acquisition_enrichment"),
                "deals_introduced": v.integer(values, "deals_introduced"),
                "deals_converted": v.integer(values, "deals_converted"),
                "ebitda_ceiling": _j(v.money(values, "ebitda_ceiling")),
                "estimated_aum": _j(v.money(values, "estimated_aum")),
                "notable_investments": v.first(values, "notable_investments"),
                "key_personnel": v.first(values, "key_personnel"),
                "relationship_warmth": v.first(values, "relationship_warmth"),
                "target_geography": v.titles(values, "target_geography"),
                "last_mandate_briefing_date": v.date(values, "last_mandate_briefing_date"),
                "prior_gcc_acquisition": v.first(values, "prior_gcc_acquisition"),
                "is_active": is_active,
                "legacy_entry_id": v.entry_id(entry),
                "raw_attio": _j(entry),
            }
            result = await session.execute(_BUYER_ROLE_UPSERT, params)
            row_id = result.scalar_one()
            if v.entry_id(entry) == entry_id:
                triggering_row_id = row_id
        await _log_activity(session, "BuyerRole", subject_uuid=triggering_row_id)
        await session.commit()


_SELLER_ROLE_UPSERT = text(
    """
    INSERT INTO seller_roles(
        org_attio_id, outreach_tier, appetite_signal, relationship_status, est_revenue,
        est_ebitda, owner_salary, valuation_low, valuation_mid, valuation_high,
        sell_timeline, readiness_score, readiness_band,
        last_attempt_date, last_attempt_channel, last_attempt_outcome, lead_quality_score,
        re_engage_date, is_active, legacy_entry_id, raw_attio
    ) VALUES (
        :org_attio_id, :outreach_tier, :appetite_signal, :relationship_status,
        CAST(:est_revenue AS jsonb), CAST(:est_ebitda AS jsonb), CAST(:owner_salary AS jsonb),
        CAST(:valuation_low AS jsonb), CAST(:valuation_mid AS jsonb),
        CAST(:valuation_high AS jsonb), :sell_timeline, :readiness_score, :readiness_band,
        :last_attempt_date, :last_attempt_channel, :last_attempt_outcome,
        :lead_quality_score, :re_engage_date, :is_active, :legacy_entry_id,
        CAST(:raw_attio AS jsonb)
    )
    ON CONFLICT (legacy_entry_id) DO UPDATE SET
        org_attio_id=excluded.org_attio_id,
        outreach_tier=excluded.outreach_tier, appetite_signal=excluded.appetite_signal,
        relationship_status=excluded.relationship_status, est_revenue=excluded.est_revenue,
        est_ebitda=excluded.est_ebitda, owner_salary=excluded.owner_salary,
        valuation_low=excluded.valuation_low, valuation_mid=excluded.valuation_mid,
        valuation_high=excluded.valuation_high, sell_timeline=excluded.sell_timeline,
        readiness_score=excluded.readiness_score, readiness_band=excluded.readiness_band,
        last_attempt_date=excluded.last_attempt_date,
        last_attempt_channel=excluded.last_attempt_channel,
        last_attempt_outcome=excluded.last_attempt_outcome,
        lead_quality_score=excluded.lead_quality_score, re_engage_date=excluded.re_engage_date,
        is_active=excluded.is_active, legacy_entry_id=excluded.legacy_entry_id,
        raw_attio=excluded.raw_attio, updated_at=now()
    RETURNING id
    """
)


async def sync_seller_role(client: AttioClient, entry_id: str) -> None:
    fetched = await get_with_retry(client, f"/lists/seller_role/entries/{entry_id}")
    org_id = v.parent_id(fetched["data"])
    winner, losers = await _reconcile_active_entry(client, "seller_role", org_id)

    async with get_sessionmaker()() as session:
        triggering_row_id = None
        for entry, is_active in [(winner, True)] + [(loser, False) for loser in losers]:
            values = v.vals(entry)
            params = {
                "org_attio_id": org_id,
                "outreach_tier": v.first(values, "outreach_tier"),
                "appetite_signal": v.first(values, "seller_appetite_signal"),
                "relationship_status": v.first(values, "relationship_status"),
                "est_revenue": _j(
                    v.money(values, "estimated_annual_revenue_aed") or v.money(values, "est_revenue")
                ),
                "est_ebitda": _j(
                    v.money(values, "estimated_ebitda_aed") or v.money(values, "est_ebitda")
                ),
                "owner_salary": _j(v.money(values, "owner_salary")),
                "valuation_low": _j(v.money(values, "valuation_low")),
                "valuation_mid": _j(v.money(values, "valuation_mid")),
                "valuation_high": _j(v.money(values, "valuation_high")),
                "sell_timeline": v.first(values, "sell_timeline"),
                "readiness_score": (
                    v.number(values, "outreach_score") or v.number(values, "readiness_score")
                ),
                "readiness_band": v.first(values, "readiness_band"),
                "last_attempt_date": v.date(values, "last_attempt_date"),
                "last_attempt_channel": v.first(values, "last_attempt_channel"),
                "last_attempt_outcome": v.first(values, "last_attempt_outcome"),
                "lead_quality_score": v.number(values, "lead_quality_score"),
                "re_engage_date": v.date(values, "re_engage_date"),
                "is_active": is_active,
                "legacy_entry_id": v.entry_id(entry),
                "raw_attio": _j(entry),
            }
            result = await session.execute(_SELLER_ROLE_UPSERT, params)
            row_id = result.scalar_one()
            if v.entry_id(entry) == entry_id:
                triggering_row_id = row_id
        await _log_activity(session, "SellerRole", subject_uuid=triggering_row_id)
        await session.commit()


# ---------------------------------------------------------------------------
# note — unified notes object (SOURCE Attio only, slug "note"; see
# `config.py`'s `attio_note_object_slug`). `notes.id` reuses the Attio
# record's own id verbatim (already a UUID), matching
# `sync-notes-from-source.ps1`'s convention -- upserts are ON CONFLICT(id).
# `buyer_role_id`/`seller_role_id` on the Attio record are the SOURCE list
# entry_id (plain text), resolved here to `buyer_roles`/`seller_roles.id` via
# their `legacy_entry_id`, same one-hop simplification that script uses.
# ---------------------------------------------------------------------------

_NOTE_UPSERT = text(
    """
    INSERT INTO notes(
        id, organization_id, person_id, buyer_role_id, seller_role_id,
        note_type, content, created_at
    ) VALUES (
        :id,
        CASE WHEN EXISTS (SELECT 1 FROM organizations WHERE attio_id = :organization_id)
             THEN :organization_id ELSE NULL END,
        CASE WHEN EXISTS (SELECT 1 FROM person WHERE attio_id = :person_id)
             THEN :person_id ELSE NULL END,
        (SELECT id FROM buyer_roles WHERE legacy_entry_id = :buyer_role_entry_id),
        (SELECT id FROM seller_roles WHERE legacy_entry_id = :seller_role_entry_id),
        :note_type, :content, COALESCE(:created_at, now())
    )
    ON CONFLICT (id) DO UPDATE SET
        organization_id=excluded.organization_id, person_id=excluded.person_id,
        buyer_role_id=excluded.buyer_role_id, seller_role_id=excluded.seller_role_id,
        note_type=excluded.note_type, content=excluded.content,
        created_at=COALESCE(excluded.created_at, notes.created_at)
    """
)


async def sync_note(client: AttioClient, record_id: str) -> None:
    fetched = await get_with_retry(client, f"/objects/note/records/{record_id}")
    data = fetched["data"]
    values = v.vals(data)
    rid = v.record_id(data)
    params = {
        "id": rid,
        "organization_id": v.ref(values, "organization_id"),
        "person_id": v.ref(values, "person_id"),
        "buyer_role_entry_id": v.first(values, "buyer_role_id"),
        "seller_role_entry_id": v.first(values, "seller_role_id"),
        "note_type": v.first(values, "note_type"),
        "content": v.first(values, "content"),
        # Slug is note_created_at, not created_at -- Attio reserves
        # created_at as a protected system attribute on every custom object.
        "created_at": v.timestamp(values, "note_created_at"),
    }
    async with get_sessionmaker()() as session:
        await session.execute(_NOTE_UPSERT, params)
        await _log_activity(session, "Note", subject_attio_id=rid)
        await session.commit()
