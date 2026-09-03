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
is `buyer_roles`/`seller_roles`' own `org_attio_id`: it's a `NOT NULL` FK
with no such guard, so it can't be nulled out -- a buyer/seller-role event
that arrives before its organization has synced is expected to fail loudly,
get caught by the background-task handler (see `router.py`), and resolve
itself on the next event or the nightly full resync. (`org_attio_id` is no
longer the row's unique key either way -- `legacy_entry_id` is, since the
2026-08-28 pluralization lets multiple entries share an org; see
`BuyerRole`/`SellerRole`'s docstrings.)

`organizations` and `person` both have a deletion story (`removed_at`,
matching the convention `sync-postgres.ps1` already established for both —
`person` needs it too since `buyer_roles.key_contact_attio_id`/
`deals.buyer_person_attio_id` reference it with `ON DELETE NO ACTION`).
`record.deleted`/`list-entry.deleted` for every other table is deliberately
out of scope here, because the existing bulk script doesn't prune those
tables either. Closing that gap is a separate, pre-existing piece of work,
not a regression this sync introduces.

Every sync function below is split into a pure "Attio data -> Postgres
params" mapper (`_organization_params`, etc. -- no I/O) and a thin
fetch-then-write wrapper (`sync_organization`, etc.) that the real-time
webhook path uses. `full_resync.py` calls the pure mappers directly on data
it already has from its own bulk page-through, instead of re-fetching each
record individually through the wrapper -- see `upsert_batch_with_retry`
below for the batched, retried write path it uses to do that.
"""

import asyncio
import json
import logging
from collections.abc import Mapping
from typing import Any

from sqlalchemy import TextClause, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Deal, Organization, Person, SellerRole
from app.modules.attio import AttioClientProtocol
from app.modules.attio.providers.attio import values as v
from app.modules.attio.providers.attio.retry import (
    get_with_retry,
    patch_with_retry,
    post_with_retry,
)
from app.modules.ddl_commands.persistence.attio_sync_types import (
    BuyerRoleParams,
    DealParams,
    NoteParams,
    OrganizationParams,
    PersonParams,
    SellerRoleParams,
)
from app.modules.ddl_commands.persistence.database import get_sessionmaker

_logger = logging.getLogger("app.modules.ddl_commands.attio_sync")

# The closed set of models this module's batch-upsert machinery
# (`_upsert_batch`/`_CONFLICT_COL`) and `full_resync.py` operate on.
SyncModel = type[Organization] | type[Person] | type[Deal] | type[BuyerRole] | type[SellerRole]


def _j(value: Any) -> str | None:
    return None if value is None else json.dumps(value)


# ---------------------------------------------------------------------------
# activities — generic change log, one row per real-time webhook sync
# ---------------------------------------------------------------------------
#
# `activities` otherwise holds curated business-interaction rows (calls,
# emails, seller-outreach attempts) from the one-off `backfill-activities.ps1`
# historical import. This adds a second, mechanical kind of row alongside
# those: "this record was created/updated", with no channel/outcome/actor to
# fill in (the webhook envelope carries only ids, never who made the change).
# Real-time webhook path only -- full_resync.py's nightly batch pass doesn't
# log one of these per row, or a routine resync of thousands of untouched
# records would flood the feed. subject_uuid (not subject_attio_id) is used
# for buyer_role/seller_role, matching backfill-activities.ps1's existing
# convention for those two UUID-keyed tables.

_ACTIVITY_INSERT = text(
    """
    INSERT INTO activities(subject_type, subject_attio_id, subject_uuid, source)
    VALUES (:subject_type, :subject_attio_id, :subject_uuid, :source)
    """
)


async def _log_activity(
    session: AsyncSession,
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


async def sync_all_users(client: AttioClientProtocol) -> int:
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


def _organization_params(data: dict) -> OrganizationParams:
    """Pure mapping from one Attio organization record (whether from a
    single-record GET or a `/records/query` bulk page -- same `values`
    shape either way, see `values.py`'s module docstring) to Postgres
    upsert params. JSONB-typed values (`funding_raised`, `raw_attio`) come
    back as native dicts here, not pre-serialized JSON strings -- callers
    executing the raw-SQL `text()` statement above must run them through
    `_j()` first (see `_for_text_sql`); the batched ORM path
    (`upsert_batch_with_retry`) takes native dicts directly.
    """
    values = v.vals(data)
    rid = v.record_id(data)
    return {
        "attio_id": rid,
        "name": v.first(values, "name") or f"Unnamed DEV Organization [{rid}]",
        "description": v.first(values, "description"),
        "type": v.titles(values, "type"),
        # client_type is multi-select on SOURCE Attio (e.g. a company can be
        # both "Fundraising" and "M&A") -- v.first() silently dropped every
        # value past the first. Postgres's client_type column is plain text
        # (not an array like type/sector_focus/categories), so every
        # selected value is comma-joined into it instead, matching
        # person.role's existing join pattern. Per-manager request,
        # 2026-08-31.
        "client_type": ", ".join(v.titles(values, "client_type")) or None,
        "sector_focus": v.titles(values, "sector_focus"),
        # SOURCE Attio's org object uses stage_focus/connection_strength
        # directly, not DEV's stage/strongest_connection_strength -- same
        # class of mismatch as _deal_params' deal_name/deal_stage/deal_owner.
        # Confirmed against a real SOURCE record's field list, 2026-08-31.
        "stage_focus": v.titles(values, "stage") or v.titles(values, "stage_focus"),
        "geographic_focus": v.titles(values, "geographic_focus"),
        "hq_country": v.first(values, "hq_country"),
        "domains": v.domains(values),
        "categories": v.titles(values, "categories"),
        "relationship_status": v.first(values, "relationship_status"),
        "connection_strength": (
            v.first(values, "strongest_connection_strength")
            or v.first(values, "connection_strength")
        ),
        "owner_attio_id": v.actor(values, "owner"),
        "last_interaction_at": v.timestamp(values, "last_interaction_at"),
        "funding_raised": v.money(values, "funding_raised"),
        "estimated_arr": v.first(values, "estimated_arr"),
        "raw_attio": data,
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


async def sync_organization(client: AttioClientProtocol, record_id: str) -> None:
    fetched = await get_with_retry(client, f"/objects/organizations/records/{record_id}")
    params = _organization_params(fetched["data"])
    async with get_sessionmaker()() as session:
        await session.execute(_ORG_UPSERT, _for_text_sql("organizations", params))
        await _log_activity(session, "Organization", subject_attio_id=params["attio_id"])
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


def _person_params(data: dict) -> PersonParams:
    values = v.vals(data)
    rid = v.record_id(data)
    roles = v.titles(values, "role") or v.titles(values, "job_title")
    return {
        "attio_id": rid,
        "name": v.first(values, "name") or f"Unnamed DEV Person [{rid}]",
        "role": ", ".join(roles) or v.first(values, "role"),
        "company_attio_id": v.ref(values, "company"),
        # DEV Attio's person object has a multi-valued email_addresses field;
        # SOURCE Attio's uses a single plain "email" field instead -- same
        # class of mismatch as _deal_params' deal_name/deal_stage/deal_owner.
        # Confirmed against a real SOURCE record's field list, 2026-08-31.
        "email": (
            [
                str(x.get("email_address"))
                for x in v.raw_items(values, "email_addresses")
                if x.get("email_address")
            ]
            or ([str(v.first(values, "email"))] if v.first(values, "email") else [])
        ),
        "linkedin": v.first(values, "linkedin"),
        "relationship_status": v.first(values, "relationship_status"),
        "connection_strength": (
            v.first(values, "strongest_connection_strength")
            or v.first(values, "connection_strength")
        ),
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
        "raw_attio": data,
    }


async def sync_person(client: AttioClientProtocol, record_id: str) -> None:
    fetched = await get_with_retry(client, f"/objects/person/records/{record_id}")
    params = _person_params(fetched["data"])
    async with get_sessionmaker()() as session:
        await session.execute(_PERSON_UPSERT, _for_text_sql("person", params))
        await _log_activity(session, "Person", subject_attio_id=params["attio_id"])
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


def _deal_params(data: dict) -> DealParams:
    values = v.vals(data)
    rid = v.record_id(data)
    buyer_id = v.ref(values, "buyer_id")
    seller_id = v.ref(values, "seller_id")
    return {
        "attio_id": rid,
        # SOURCE Attio's custom "deal" object uses different slugs than DEV's
        # native "deals" object for these three fields (deal_name/deal_stage/
        # deal_owner vs name/stage/owner) -- same reason `value` below already
        # falls back to `deal_value`. Confirmed against a real SOURCE record's
        # field list, 2026-08-31.
        "name": (
            v.first(values, "name") or v.first(values, "deal_name") or f"Unnamed DEV Deal [{rid}]"
        ),
        "stage": v.first(values, "stage") or v.first(values, "deal_stage"),
        "stage_changed_at": v.timestamp(values, "stage_changed_at"),
        # Resolved against the real tables below, at write time, since a
        # buyer/seller id here can point at either an organization or a
        # person depending on the deal -- see the CASE WHEN EXISTS guards in
        # `_DEAL_UPSERT` and the equivalent per-row check in `_deal_fk_params`.
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "owner_attio_id": v.actor(values, "owner") or v.actor(values, "deal_owner"),
        "value": v.money(values, "value") or v.money(values, "deal_value"),
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
        "universe_constructed": v.boolean(values, "universe_constructed") or False,
        "universe_size": v.integer(values, "universe_size"),
        "shortlist_approved": v.boolean(values, "shortlist_approved") or False,
        "shortlist_size": v.integer(values, "shortlist_size"),
        "tier1_contacted": v.integer(values, "tier1_contacted"),
        "responses": v.integer(values, "responses"),
        "counterparty_interested": v.integer(values, "counterparty_interested"),
        "mandate_start_date": v.date(values, "start_date"),
        "mandate_expiry_date": v.date(values, "expiry_date"),
        "retainer_amount": v.money(values, "retainer_amount"),
        "source_mandate_entry_id": v.first(values, "source_mandate_entry_id"),
        "raw_attio": data,
    }


async def sync_deal(
    client: AttioClientProtocol, record_id: str, *, object_slug: str = "deals"
) -> None:
    """`object_slug` is the actual Attio object api_slug to fetch from --
    "deals" (DEV's native object, the default) or "deal" (SOURCE's custom
    object, singular -- see `config.py`'s `attio_deal_object_slug`). Both map
    to the same `deals` Postgres table either way."""
    fetched = await get_with_retry(client, f"/objects/{object_slug}/records/{record_id}")
    params = _deal_params(fetched["data"])
    async with get_sessionmaker()() as session:
        await session.execute(_DEAL_UPSERT, _for_text_sql("deals", params))
        await _log_activity(session, "Deal", subject_attio_id=params["attio_id"])
        await session.commit()


# ---------------------------------------------------------------------------
# buyer_role / seller_role — duplicate-aware via `is_active`
# ---------------------------------------------------------------------------


async def _fetch_siblings(client: AttioClientProtocol, list_slug: str, org_id: str) -> list[dict]:
    """Every entry in `list_slug` whose parent is `org_id`. Pages the whole
    list and filters client-side (see `dispatch.py`'s module docstring for
    why — Attio's parent-record filter syntax wasn't confirmed reliable
    enough to bet a write-back on), same technique `sync-postgres.ps1` and
    `crm-sync/scripts/_internal/lists.ps1` already use successfully. Used by
    the webhook path only -- `full_resync.py` already has every entry from
    its own page-through and groups siblings itself (see
    `group_entries_by_org`), so it calls `_reconcile_active_entry` directly
    with a siblings list instead of going through this."""
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


def group_entries_by_org(entries: list[dict]) -> dict[str, list[dict]]:
    """Groups a list-wide page-through's entries by parent org id — lets
    `full_resync.py` compute every org's full sibling list from the one pass
    it already makes, instead of `_reconcile_active_entry` re-paging the
    whole list once per org."""
    by_org: dict[str, list[dict]] = {}
    for entry in entries:
        by_org.setdefault(v.parent_id(entry), []).append(entry)
    return by_org


async def _reconcile_active_entry(
    client: AttioClientProtocol, list_slug: str, siblings: list[dict]
) -> list[dict]:
    """Ensures exactly one entry among `siblings` (all belonging to the same
    org) is `is_active`, flipping Attio's own flags (not just Postgres's) if
    needed — `is_active` is a real Attio field other consumers read too, so
    the correction has to land there, not just in our mirror. Newest
    `created_at` wins, the same tiebreak `lists.ps1` already applies
    elsewhere.

    Postgres mirrors every DEV Attio entry now, one row each keyed by
    `legacy_entry_id` (buyer_roles/seller_roles' 2026-08-28 pluralization --
    `org_attio_id` is no longer unique) rather than collapsing to a single
    row per org, so this returns every sibling, winner first, instead of
    just the winner: the caller writes one Postgres row per entry, with
    `is_active` set explicitly from each entry's position here (winner=True,
    every loser=False) rather than re-read from Attio -- that avoids relying
    on the PATCH above having already taken effect by the time it's read.
    """
    if not siblings:
        raise ValueError(f"no {list_slug} entries found for this org")
    siblings = sorted(siblings, key=lambda e: e.get("created_at") or "", reverse=True)
    winner, *losers = siblings

    org_id = v.parent_id(winner)
    if v.boolean(v.vals(winner), "is_active") is not True:
        _logger.info(
            "full resync: correcting %s is_active=True for org %s entry %s",
            list_slug,
            org_id,
            v.entry_id(winner),
        )
        await patch_with_retry(
            client,
            f"/lists/{list_slug}/entries/{v.entry_id(winner)}",
            {"data": {"entry_values": {"is_active": True}}},
        )
    for loser in losers:
        if v.boolean(v.vals(loser), "is_active") is not False:
            _logger.info(
                "full resync: correcting %s is_active=False for org %s entry %s",
                list_slug,
                org_id,
                v.entry_id(loser),
            )
            await patch_with_retry(
                client,
                f"/lists/{list_slug}/entries/{v.entry_id(loser)}",
                {"data": {"entry_values": {"is_active": False}}},
            )
    return siblings


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
        is_active=excluded.is_active,
        raw_attio=excluded.raw_attio, updated_at=now()
    RETURNING id
    """
)


def _buyer_role_params(org_id: str, entry: dict, is_active: bool) -> BuyerRoleParams:
    values = v.vals(entry)
    return {
        "org_attio_id": org_id,
        "model": v.first(values, "model"),
        "mandate_status": v.first(values, "mandate_status"),
        "ebitda_floor": v.money(values, "ebitda_floor"),
        "check_size_min": v.money(values, "check_size_min"),
        "check_size_max": v.money(values, "check_size_max"),
        "ev_ceiling": v.money(values, "ev_ceiling"),
        "deal_structure_tolerance": v.first(values, "deal_structure_tolerance"),
        "earnout_tolerance": v.boolean(values, "earnout_tolerance"),
        "profitable_only": v.boolean(values, "profitable_only"),
        "investment_strategy": v.first(values, "investment_strategy"),
        "notes": v.first(values, "notes"),
        "key_contact_attio_id": v.ref(values, "key_contact"),
        "acquisition_enrichment": v.first(values, "acquisition_enrichment"),
        "deals_introduced": v.integer(values, "deals_introduced"),
        "deals_converted": v.integer(values, "deals_converted"),
        "ebitda_ceiling": v.money(values, "ebitda_ceiling"),
        "estimated_aum": v.money(values, "estimated_aum"),
        "notable_investments": v.first(values, "notable_investments"),
        "key_personnel": v.first(values, "key_personnel"),
        "relationship_warmth": v.first(values, "relationship_warmth"),
        "target_geography": v.titles(values, "target_geography"),
        "last_mandate_briefing_date": v.date(values, "last_mandate_briefing_date"),
        "prior_gcc_acquisition": v.first(values, "prior_gcc_acquisition"),
        "is_active": is_active,
        "legacy_entry_id": v.entry_id(entry),
        "raw_attio": entry,
    }


async def sync_buyer_role(client: AttioClientProtocol, entry_id: str) -> None:
    fetched = await get_with_retry(client, f"/lists/buyer_role/entries/{entry_id}")
    org_id = v.parent_id(fetched["data"])
    siblings = await _fetch_siblings(client, "buyer_role", org_id)
    reconciled = await _reconcile_active_entry(client, "buyer_role", siblings)
    async with get_sessionmaker()() as session:
        triggering_row_id = None
        for i, entry in enumerate(reconciled):
            params = _buyer_role_params(org_id, entry, is_active=(i == 0))
            result = await session.execute(_BUYER_ROLE_UPSERT, _for_text_sql("buyer_roles", params))
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
        re_engage_date, is_active,
        years_active, funding_stage, revenue_last_full_year, revenue_year_before,
        gross_margin_pct, ebitda_deducts_salary, annual_rent_cost,
        largest_customer_revenue_pct, repeat_revenue_pct, location_count,
        legacy_entry_id, raw_attio
    ) VALUES (
        :org_attio_id, :outreach_tier, :appetite_signal, :relationship_status,
        CAST(:est_revenue AS jsonb), CAST(:est_ebitda AS jsonb), CAST(:owner_salary AS jsonb),
        CAST(:valuation_low AS jsonb), CAST(:valuation_mid AS jsonb),
        CAST(:valuation_high AS jsonb), :sell_timeline, :readiness_score, :readiness_band,
        :last_attempt_date, :last_attempt_channel, :last_attempt_outcome,
        :lead_quality_score, :re_engage_date, :is_active,
        :years_active, :funding_stage, CAST(:revenue_last_full_year AS jsonb),
        CAST(:revenue_year_before AS jsonb), :gross_margin_pct, :ebitda_deducts_salary,
        CAST(:annual_rent_cost AS jsonb), :largest_customer_revenue_pct, :repeat_revenue_pct,
        :location_count, :legacy_entry_id,
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
        is_active=excluded.is_active,
        years_active=excluded.years_active, funding_stage=excluded.funding_stage,
        revenue_last_full_year=excluded.revenue_last_full_year,
        revenue_year_before=excluded.revenue_year_before,
        gross_margin_pct=excluded.gross_margin_pct,
        ebitda_deducts_salary=excluded.ebitda_deducts_salary,
        annual_rent_cost=excluded.annual_rent_cost,
        largest_customer_revenue_pct=excluded.largest_customer_revenue_pct,
        repeat_revenue_pct=excluded.repeat_revenue_pct, location_count=excluded.location_count,
        raw_attio=excluded.raw_attio, updated_at=now()
    RETURNING id
    """
)


def _seller_role_params(org_id: str, entry: dict, is_active: bool) -> SellerRoleParams:
    values = v.vals(entry)
    return {
        "org_attio_id": org_id,
        "outreach_tier": v.first(values, "outreach_tier"),
        # SOURCE Attio's seller_role list uses appetite_signal directly, not
        # DEV's seller_appetite_signal -- same class of mismatch as
        # _deal_params' deal_name/deal_stage/deal_owner. Confirmed against a
        # real SOURCE record's field list, 2026-08-31.
        "appetite_signal": (
            v.first(values, "seller_appetite_signal") or v.first(values, "appetite_signal")
        ),
        "relationship_status": v.first(values, "relationship_status"),
        "est_revenue": (
            v.money(values, "estimated_annual_revenue_aed") or v.money(values, "est_revenue")
        ),
        "est_ebitda": v.money(values, "estimated_ebitda_aed") or v.money(values, "est_ebitda"),
        "owner_salary": v.money(values, "owner_salary"),
        "valuation_low": v.money(values, "valuation_low"),
        "valuation_mid": v.money(values, "valuation_mid"),
        "valuation_high": v.money(values, "valuation_high"),
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
        # Lead Magnet questionnaire fields (0fca196) -- same money shape as
        # est_revenue/est_ebitda/owner_salary above: {"amount", "currency"}
        # or NULL, never fabricated when absent.
        "years_active": v.integer(values, "years_active"),
        "funding_stage": v.first(values, "funding_stage"),
        "revenue_last_full_year": v.money(values, "revenue_last_full_year"),
        "revenue_year_before": v.money(values, "revenue_year_before"),
        "gross_margin_pct": v.number(values, "gross_margin_pct"),
        "ebitda_deducts_salary": v.boolean(values, "ebitda_deducts_salary"),
        "annual_rent_cost": v.money(values, "annual_rent_cost"),
        "largest_customer_revenue_pct": v.number(values, "largest_customer_revenue_pct"),
        "repeat_revenue_pct": v.number(values, "repeat_revenue_pct"),
        "location_count": v.integer(values, "location_count"),
        "legacy_entry_id": v.entry_id(entry),
        "raw_attio": entry,
    }


async def sync_seller_role(client: AttioClientProtocol, entry_id: str) -> None:
    fetched = await get_with_retry(client, f"/lists/seller_role/entries/{entry_id}")
    org_id = v.parent_id(fetched["data"])
    siblings = await _fetch_siblings(client, "seller_role", org_id)
    reconciled = await _reconcile_active_entry(client, "seller_role", siblings)
    async with get_sessionmaker()() as session:
        triggering_row_id = None
        for i, entry in enumerate(reconciled):
            params = _seller_role_params(org_id, entry, is_active=(i == 0))
            result = await session.execute(
                _SELLER_ROLE_UPSERT, _for_text_sql("seller_roles", params)
            )
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
# their `legacy_entry_id`, same one-hop simplification that script uses. No
# `raw_attio` column on this table (unlike every other model here), so it
# stays out of the generic `_upsert_batch`/`_CONFLICT_COL` batch machinery --
# `full_resync.py` syncs it with a plain per-row loop instead.
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


def _note_params(data: dict) -> NoteParams:
    values = v.vals(data)
    return {
        "id": v.record_id(data),
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


async def sync_note(client: AttioClientProtocol, record_id: str) -> None:
    fetched = await get_with_retry(client, f"/objects/note/records/{record_id}")
    params = _note_params(fetched["data"])
    async with get_sessionmaker()() as session:
        await session.execute(_NOTE_UPSERT, params)
        await _log_activity(session, "Note", subject_attio_id=params["id"])
        await session.commit()


# ---------------------------------------------------------------------------
# Batched writes for full_resync.py — multi-row `INSERT ... ON CONFLICT`
# instead of one commit per row, with a same-round-trip `RETURNING` for the
# content-consistency check, and a retry-then-per-row-fallback so one bad
# row can't sink an entire page.
# ---------------------------------------------------------------------------

# text()-SQL params need JSONB-typed values pre-serialized to strings (the
# statements above CAST(:x AS jsonb)); the ORM Core batch path below takes
# native dicts directly, since SQLAlchemy's JSONB type serializes them
# itself. `_organization_params`/etc. return native dicts so both paths can
# share one mapping function -- this converts for the text()-SQL callers.
_JSONB_FIELDS = {
    "organizations": ("funding_raised", "raw_attio"),
    "person": ("raw_attio",),
    "deals": ("value", "retainer_amount", "raw_attio"),
    "buyer_roles": (
        "ebitda_floor",
        "check_size_min",
        "check_size_max",
        "ev_ceiling",
        "ebitda_ceiling",
        "estimated_aum",
        "raw_attio",
    ),
    "seller_roles": (
        "est_revenue",
        "est_ebitda",
        "owner_salary",
        "valuation_low",
        "valuation_mid",
        "valuation_high",
        "revenue_last_full_year",
        "revenue_year_before",
        "annual_rent_cost",
        "raw_attio",
    ),
}


def _for_text_sql(table_name: str, params: Mapping[str, Any]) -> dict:
    jsonb_keys = _JSONB_FIELDS[table_name]
    return {k: (_j(val) if k in jsonb_keys else val) for k, val in params.items()}


_MODEL_TABLE: dict[SyncModel, str] = {
    Organization: "organizations",
    Person: "person",
    Deal: "deals",
    BuyerRole: "buyer_roles",
    SellerRole: "seller_roles",
}
_MODEL_UPSERT_SQL: dict[SyncModel, TextClause] = {
    Organization: _ORG_UPSERT,
    Person: _PERSON_UPSERT,
    Deal: _DEAL_UPSERT,
    BuyerRole: _BUYER_ROLE_UPSERT,
    SellerRole: _SELLER_ROLE_UPSERT,
}
_CONFLICT_COL: dict[SyncModel, str] = {
    Organization: "attio_id",
    Person: "attio_id",
    Deal: "attio_id",
    # legacy_entry_id, not org_attio_id: buyer_roles/seller_roles.org_attio_id
    # lost its UNIQUE constraint in the 2026-08-28 pluralization (Postgres
    # now mirrors every DEV Attio entry, one row each -- see BuyerRole's
    # docstring) -- org_attio_id is a plain indexed FK now, not a valid
    # ON CONFLICT target.
    BuyerRole: "legacy_entry_id",
    SellerRole: "legacy_entry_id",
}
# organizations.removed_at is Attio-owned (cleared whenever a currently-live
# record is (re)written -- see the raw-SQL upserts' `removed_at=NULL`) but
# isn't one of `_organization_params`' output keys, so the generic
# `excluded.<col>` derivation below would resolve it to NULL by accident
# (Postgres treats a column missing from a multi-row INSERT's value list as
# its default in `excluded`). Set it explicitly instead of relying on that.
_EXTRA_UPDATE_COLS = {
    Organization: {"removed_at": None},
}
# Never derive these from `excluded.<col>` -- `rows` never carries a value
# for any of them (they're all server-generated), so the generic derivation
# below would resolve every one of them to NULL on conflict. `updated_at`
# gets `now()` explicitly instead (matching every raw-SQL upsert above);
# `id` (BuyerRole/SellerRole's real primary key, separate from their
# `org_attio_id` conflict column) and `created_at` are just left alone.
_NEVER_UPDATE_COLS = {"id", "created_at", "updated_at"}


def _resolve_ref(value: str | None, valid_ids: set[str]) -> str | None:
    """Mirrors a `CASE WHEN EXISTS (...) THEN x ELSE NULL END` guard for the
    batch/ORM path, where a per-row correlated subquery isn't expressible
    inside one multi-row `VALUES` list — resolved instead against id sets
    already known this run, from earlier entity types' own bulk fetch
    (organizations/people/users all sync before deals/buyer_role/
    seller_role, per `full_resync.py`'s fixed entity-type order)."""
    return value if value in valid_ids else None


def _organization_batch_params(data: dict, user_ids: set[str]) -> dict:
    params: dict = dict(_organization_params(data))
    params["owner_attio_id"] = _resolve_ref(params["owner_attio_id"], user_ids)
    return params


def _person_batch_params(data: dict, org_ids: set[str], user_ids: set[str]) -> dict:
    params: dict = dict(_person_params(data))
    params["company_attio_id"] = _resolve_ref(params["company_attio_id"], org_ids)
    params["owner_attio_id"] = _resolve_ref(params["owner_attio_id"], user_ids)
    return params


def _deal_batch_params(
    data: dict, org_ids: set[str], person_ids: set[str], user_ids: set[str]
) -> dict:
    """Batch-path variant of `_deal_params`. `_deal_params` leaves
    `buyer_id`/`seller_id` ambiguous (could be an organization or a person)
    for the webhook path's `_DEAL_UPSERT`, which resolves each with a
    per-statement `CASE WHEN EXISTS` -- a multi-row `VALUES` list can't
    express that conditional per row generically, so the batch path
    resolves it here instead, using id sets already known this run."""
    params: dict = dict(_deal_params(data))
    buyer_id = params.pop("buyer_id")
    seller_id = params.pop("seller_id")
    params["buyer_organization_attio_id"] = _resolve_ref(buyer_id, org_ids)
    params["buyer_person_attio_id"] = _resolve_ref(buyer_id, person_ids)
    params["seller_organization_attio_id"] = _resolve_ref(seller_id, org_ids)
    params["owner_attio_id"] = _resolve_ref(params["owner_attio_id"], user_ids)
    return params


def _buyer_role_batch_params(
    org_id: str, entry: dict, is_active: bool, person_ids: set[str]
) -> dict:
    params: dict = dict(_buyer_role_params(org_id, entry, is_active))
    params["key_contact_attio_id"] = _resolve_ref(params["key_contact_attio_id"], person_ids)
    return params


async def _upsert_batch(model: SyncModel, rows: list[dict]) -> dict[str, dict]:
    """Batch-upserts `rows` for `model` in one round trip and returns
    `{conflict_key: raw_attio_as_written}`, built from the same statement's
    `RETURNING` clause -- for the caller's content-consistency check.
    Compare by key, never by list position: Postgres does not guarantee
    `RETURNING` preserves multi-row `VALUES` input order.
    """
    if not rows:
        return {}
    conflict_col = _CONFLICT_COL[model]
    stmt = pg_insert(model).values(rows)
    # Only update columns the mapper actually populated (every row shares the
    # same keys -- one mapper produced them all). A column the model has but
    # the mapper doesn't map yet (e.g. a field added to the schema before the
    # sync code catches up) must never appear here: it was never in the
    # INSERT's VALUES either, so Postgres's `excluded` row has it as NULL --
    # blindly setting `col=excluded.col` for every model column would silently
    # wipe that column to NULL on every existing row's conflict-update.
    mapped_cols = set(rows[0])
    update_cols = {
        c.name: getattr(stmt.excluded, c.name)
        for c in model.__table__.columns
        if c.name in mapped_cols and c.name != conflict_col and c.name not in _NEVER_UPDATE_COLS
    }
    update_cols["updated_at"] = func.now()
    update_cols.update(_EXTRA_UPDATE_COLS.get(model, {}))
    # Skip the write entirely when nothing actually changed (Stripe's
    # reconciliation-blog advice: compare content, not timestamps, before
    # writing) -- avoids rewriting all ~8,000 rows every night regardless of
    # whether Attio's data moved, and the bump-free `updated_at` means a row
    # genuinely untouched tonight doesn't look "just synced" to anything
    # watching that column. `removed_at IS NOT NULL` forces the write through
    # anyway for a soft-deleted row that reappears with byte-identical
    # raw_attio, so its `removed_at=NULL` reset (see _EXTRA_UPDATE_COLS)
    # still lands -- content-only comparison would otherwise skip it forever.
    where = stmt.excluded.raw_attio.is_distinct_from(model.raw_attio)
    removed_at = getattr(model, "removed_at", None)
    if removed_at is not None:
        where = where | removed_at.is_not(None)
    stmt = stmt.on_conflict_do_update(index_elements=[conflict_col], set_=update_cols, where=where)
    conflict_column_obj = getattr(model, conflict_col)
    stmt = stmt.returning(conflict_column_obj, model.raw_attio)
    async with get_sessionmaker()() as session:
        result = await session.execute(stmt)
        returned = {row[0]: row[1] for row in result}
        await session.commit()
        return returned


async def upsert_batch_with_retry(
    model: SyncModel, rows: list[dict], page_label: str = ""
) -> tuple[int, int, dict[str, dict]]:
    """Batches `rows` for `model`; on a transient DB error, retries the
    whole batch with backoff; on any other error (e.g. one malformed row),
    falls back to the existing single-row `text()` upsert one row at a time
    so a single bad row is reported and skipped instead of losing the whole
    page. Returns `(ok, failed, returned_by_key)` -- the last only populated
    on the batch-success path, for the content-consistency check. `page_label`
    is purely for tracing (e.g. "page 2/7") when a caller writes several
    pages of the same table concurrently -- optional, defaults to blank.
    """
    conflict_col = _CONFLICT_COL[model]
    table_name = _MODEL_TABLE[model]
    for attempt in range(3):
        try:
            returned = await _upsert_batch(model, rows)
            return len(rows), 0, returned
        except OperationalError:
            if attempt == 2:
                break
            delay = min(30, 5 * (attempt + 1))
            _logger.warning(
                "full resync: %s %s batch upsert attempt %d failed (transient), retrying in %ds",
                table_name,
                page_label,
                attempt + 1,
                delay,
                exc_info=True,
            )
            await asyncio.sleep(delay)
        except Exception:
            break  # not transient (e.g. a bad row) -- don't retry the whole batch again

    _logger.warning(
        "full resync: batch upsert failed for %s %s (%d rows), falling back to per-row",
        table_name,
        page_label,
        len(rows),
    )
    ok = failed = 0
    single_stmt = _MODEL_UPSERT_SQL[model]
    async with get_sessionmaker()() as session:
        for row in rows:
            try:
                await session.execute(single_stmt, _for_text_sql(table_name, row))
                await session.commit()
                ok += 1
            except Exception:
                await session.rollback()
                failed += 1
                _logger.error(
                    "full resync: failed to upsert row %r", row.get(conflict_col), exc_info=True
                )
    return ok, failed, {}


class AttioSyncRepository:
    """Implements `application.ports.attio_sync.AttioSyncRepositoryPort` by
    delegating to this module's own free functions — kept as thin methods
    here rather than turning the free functions themselves into methods, so
    `full_resync.py`'s direct calls to the free functions (its own bulk
    page-through, not per-record dispatch) are unaffected.
    """

    async def sync_organization(self, client: AttioClientProtocol, record_id: str) -> None:
        await sync_organization(client, record_id)

    async def sync_person(self, client: AttioClientProtocol, record_id: str) -> None:
        await sync_person(client, record_id)

    async def sync_deal(
        self, client: AttioClientProtocol, record_id: str, *, object_slug: str = "deals"
    ) -> None:
        await sync_deal(client, record_id, object_slug=object_slug)

    async def sync_note(self, client: AttioClientProtocol, record_id: str) -> None:
        await sync_note(client, record_id)

    async def sync_buyer_role(self, client: AttioClientProtocol, entry_id: str) -> None:
        await sync_buyer_role(client, entry_id)

    async def sync_seller_role(self, client: AttioClientProtocol, entry_id: str) -> None:
        await sync_seller_role(client, entry_id)

    async def delete_organization(self, record_id: str) -> None:
        await delete_organization(record_id)

    async def delete_person(self, record_id: str) -> None:
        await delete_person(record_id)
