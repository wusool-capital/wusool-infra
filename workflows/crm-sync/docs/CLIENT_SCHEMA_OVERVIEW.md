# Wusool CRM and Data Platform Schema

## Executive overview

Wusool uses Attio and PostgreSQL together as one connected data platform. Attio is the working CRM used by the team to manage organizations, people, opportunities, mandates, and relationships. PostgreSQL is the structured data layer used for synchronization, analysis, scoring, automation, research, and document workflows.

The two platforms have different responsibilities but share common record identifiers. This allows CRM activity in Attio to connect reliably with enriched and machine-generated information in PostgreSQL.

### How the platforms work together

1. The team creates and manages core CRM information in Attio.
2. Shared records are mirrored into PostgreSQL using Attio identifiers.
3. PostgreSQL stores analytical, enrichment, event, scoring, and automation data.
4. Selected operational results can be synchronized back to Attio for use in day-to-day workflows.

### How to read this document

- **Platform overview** maps the principal Attio entities to their PostgreSQL tables.
- **Attio schema** describes the CRM objects, lists, fields, and relationships visible to business users.
- **PostgreSQL schema** describes the underlying tables, data types, keys, and relationships used by the platform.
- **Data relationships** explains how records connect across the model.
- **Data ownership** identifies which platform is responsible for each category of information.

## Platform overview

| Attio entity | Business purpose | Entity type | PostgreSQL table |
|---|---|---|---|
| Organization | Companies and institutions in the Wusool network | object | `organizations` |
| Person | Individual contacts and their organization relationships | object | `people` |
| User | Authorized workspace members and record owners | workspace-members | `users` |
| buyer_role | Buyer profile, investment criteria, and mandate readiness | list | `buyer_roles` |
| seller_role | Seller profile, valuation indicators, and outreach progress | list | `seller_roles` |
| investor_lender_role | Investor or lender preferences and areas of focus | list | `investor_lender_roles` |
| Deal | Transaction opportunities and pipeline progression | object | `deals` |
| Mandate | Buy-side or sell-side engagements and execution progress | list | `mandates` |

## Attio schema

Attio contains the client-facing CRM records, relationship information, pipeline data, and role-based workflows.

### Organization

Type: object | API identifier: `organizations`

| Field | Type | Data responsibility | Relationship |
|---|---|---|---|
| `attio_id` | `text` | key | - |
| `legacy_attio_id` | `text` | key | - |
| `name` | `text` | attio | - |
| `description` | `text` | attio | - |
| `type` | `enum[]` | attio | - |
| `client_type` | `enum` | attio | - |
| `sector_focus` | `enum[]` | attio | - |
| `stage_focus` | `enum[]` | attio | - |
| `geographic_focus` | `enum[]` | attio | - |
| `hq_country` | `text` | attio | - |
| `domains` | `text[]` | attio | - |
| `logo_url` | `text` | attio | - |
| `categories` | `enum[]` | attio | - |
| `relationship_status` | `enum` | attio | - |
| `connection_strength` | `enum` | attio | - |
| `owner` | `user-reference` | key | User |
| `last_interaction_at` | `timestamp` | both | - |
| `funding_raised` | `money` (USD) | attio | - |
| `estimated_arr` | `enum` | attio | - |
| `angellist` | `text` | attio | - |
| `facebook` | `text` | attio | - |
| `instagram` | `text` | attio | - |
| `twitter` | `text` | attio | - |
| `twitter_follower_count` | `integer` | attio | - |
| `foundation_date` | `date` | attio | - |
| `employee_range` | `enum` | attio | - |
| `linkedin` | `text` | attio | - |
| `ticket_size` | `text` | attio | - |
| `lead_source` | `enum` (Inbound / Outbound) | attio | - |
| `is_active` | `boolean` | attio | - |

### Person

Type: object | API identifier: `person`

| Field | Type | Data responsibility | Relationship |
|---|---|---|---|
| `attio_id` | `text` | key | - |
| `legacy_attio_id` | `text` | key | - |
| `name` | `text` | attio | - |
| `role` | `enum[]` | attio | - |
| `company` | `record-reference` | key | Organization |
| `email` | `text[]` | attio | - |
| `linkedin` | `text` | attio | - |
| `relationship_status` | `enum` | attio | - |
| `connection_strength` | `enum` | attio | - |
| `owner` | `user-reference` | key | User |
| `past_employers` | `jsonb` | postgres | - |
| `education` | `jsonb` | postgres | - |
| `enrichment` | `jsonb` | postgres | - |
| `last_interaction_at` | `timestamp` | both | - |
| `job_title` | `text` | attio | - |
| `contact_type` | `enum` | attio | - |
| `phone` | `text` | attio | - |
| `avatar_url` | `text` | attio | - |
| `angellist` | `text` | attio | - |
| `facebook` | `text` | attio | - |
| `instagram` | `text` | attio | - |
| `twitter` | `text` | attio | - |
| `twitter_follower_count` | `integer` | attio | - |

### User

Type: workspace-members

| Field | Type | Data responsibility | Relationship |
|---|---|---|---|
| `attio_id` | `text` | key | - |
| `name` | `text` | attio | - |
| `email` | `text` | attio | - |
| `access` | `enum` | attio | - |
| `active` | `boolean` | both | - |

### buyer_role

Type: list | API identifier: `buyer_role` | Parent: `organizations`

| Field | Type | Data responsibility | Relationship |
|---|---|---|---|
| `id` | `uuid` | key | - |
| `org_id` | `record-reference` | key | Organization |
| `model` | `enum` | attio | - |
| `mandate_status` | `enum` | attio | - |
| `ebitda_floor` | `money` | attio | - |
| `check_size_min` | `money` | attio | - |
| `check_size_max` | `money` | attio | - |
| `ev_ceiling` | `money` | attio | - |
| `deal_structure_tolerance` | `enum` | attio | - |
| `earnout_tolerance` | `boolean` | attio | - |
| `profitable_only` | `boolean` | attio | - |
| `investment_strategy` | `text` | attio | - |
| `notes` | `text` | attio | - |
| `key_contact` | `record-reference` | key | Person |
| `acquisition_enrichment` | `text` | both | - |
| `deals_introduced` | `integer` | both | - |
| `deals_converted` | `integer` | both | - |
| `is_active` | `boolean` | both | - |
| `legacy_entry_id` | `text` | key | - |
| `ebitda_ceiling` | `money` | attio | - |
| `estimated_aum` | `money` | attio | - |
| `notable_investments` | `text` | attio | - |
| `key_personnel` | `text` | attio | - |
| `relationship_warmth` | `enum` | attio | - |
| `target_geography` | `enum[]` (multiselect) | attio | - |
| `last_mandate_briefing_date` | `date` | attio | - |
| `prior_gcc_acquisition` | `text` | attio | - |

`typical_check_size` dropped 2026-08-23 (see `migration-decisions.json`'s `dropped_fields`) — redundant with `check_size_min`/`check_size_max` above.

### seller_role

Type: list | API identifier: `seller_role` | Parent: `organizations`

| Field | Type | Data responsibility | Relationship |
|---|---|---|---|
| `id` | `uuid` | key | - |
| `org_id` | `record-reference` | key | Organization |
| `outreach_tier` | `enum` | attio | - |
| `appetite_signal` | `enum` | attio | - |
| `relationship_status` | `enum` | attio | - |
| `est_revenue` | `money` | attio | - |
| `est_ebitda` | `money` | attio | - |
| `owner_salary` | `money` | attio | - |
| `valuation_low` | `money` | attio | - |
| `valuation_mid` | `money` | attio | - |
| `valuation_high` | `money` | attio | - |
| `sell_timeline` | `enum` | attio | - |
| `readiness_score` | `numeric` | attio | - |
| `readiness_band` | `enum` | attio | - |
| `mandate_id` | `record-reference` | both | Mandate (historical rows only, see retired Mandate note above) |
| `last_attempt_date` | `date` | both | - |
| `last_attempt_channel` | `enum` | both | - |
| `last_attempt_outcome` | `enum` | both | - |
| `lead_quality_score` | `numeric` | both | - |
| `re_engage_date` | `date` | both | - |
| `is_active` | `boolean` | both | - |
| `legacy_entry_id` | `text` | key | - |

### investor_lender_role

Type: list | API identifier: `investor_lender_role` | Parent: `companies`

| Field | Type | Data responsibility | Relationship |
|---|---|---|---|
| `org_id` | `record-reference` | key | Organization |
| `investor_type` | `enum` | attio | - |
| `stage_focus` | `enum[]` | attio | - |
| `sector_focus` | `enum[]` | attio | - |
| `interests` | `text` | attio | - |
| `facility_type` | `text` | attio | - |
| `activity_level` | `enum` | attio | - |

### Deal

Type: object | API identifier: `deals`

| Field | Type | Data responsibility | Relationship |
|---|---|---|---|
| `attio_id` | `text` | key | - |
| `legacy_attio_id` | `text` | key | - |
| `name` | `text` | attio | - |
| `stage` | `enum` | attio | - |
| `stage_changed_at` | `timestamp` | attio | - |
| `time_in_stage` | `numeric` | attio | - |
| `buyer_id` | `record-reference` | key | OrganizationOrPerson |
| `seller_id` | `record-reference` | key | Organization |
| `owner` | `user-reference` | key | User |
| `value` | `money` | attio | - |
| `teaser_status` | `enum` | attio | - |
| `nda_count` | `integer` | attio | - |
| `cim_ready` | `boolean` | attio | - |
| `deal_memo_ready` | `boolean` | attio | - |
| `contract_signed_date` | `date` | attio | - |
| `exclusivity_date` | `date` | attio | - |
| `next_task` | `text` | attio | - |
| `data_room_substatus` | `enum` | both | - |
| `comparables` | `jsonb` | postgres | - |
| `assigned_advisor` | `enum[]` (multiselect) | attio | - |
| `deal_type` | `enum` (`Buy-side` / `Sell-side`) | attio | - |
| `universe_constructed` | `boolean` | attio | - |
| `universe_size` | `integer` | attio | - |
| `shortlist_approved` | `boolean` | attio | - |
| `shortlist_size` | `integer` | attio | - |
| `tier1_contacted` | `integer` | attio | - |
| `responses` | `integer` | attio | - |
| `counterparty_interested` | `integer` | attio | - |
| `start_date` | `date` | attio | - |
| `expiry_date` | `date` | attio | - |
| `retainer_amount` | `money` (AED) | attio | - |
| `source_mandate_entry_id` | `text` | key | Idempotency key for the one-time Mandate migration below — not a real business field. |

`stage` includes a `Mandate Active` status: a signed mandate still sourcing
candidates, no specific counterparty locked in yet. Distinct from
`Mandate Signed`, which already implies a specific counterparty and signed
terms — the two "mandate" states were never the same thing (see the retired
Mandate section below).

### Mandate — retired 2026-08-23, merged into Deal

Type: list | API identifier: `mandates` | Parent: `organizations`

**Status: retired.** Every Mandate entry now becomes its own Deal record
(`stage` = `Mandate Active`) instead of a separate list attached to an
Organization — see `scripts/_internal/objects.ps1`'s `Invoke-Deals
-MigrateMandates` for the one-time migration logic (idempotent via
`source_mandate_entry_id`, safe to re-run). Rationale: the two-tier model
(one Mandate → many candidate Deals) was designed for but never actually
used — neither of the 2 real DEV Mandate entries had a single Deal record
linked to them at the time of the merge.

`phase` was deliberately **not** carried over to Deal: it's a manually-typed
label that only restates what `universe_constructed`/`universe_size`/
`shortlist_approved`/`shortlist_size`/`tier1_contacted`/`responses` already
show, and can silently drift out of sync with those numbers. `sellers_interested`
was renamed to `counterparty_interested` on Deal since "sellers" only makes
sense framed from a buy-side mandate, and the merged model needs one field
that reads correctly for both `Buy-side` and `Sell-side` deals.
`assigned_advisor` reuses Deal's existing `Hugo`/`Jules`/`Ramzy` multiselect
enum rather than Mandate's `user-reference[]` type — Attio doesn't support
changing a field's type in place, and a second parallel "who's the advisor"
field on Deal would be worse than picking one.

| Field | Type | Data responsibility | Relationship |
|---|---|---|---|
| `id` | `uuid` | key | - |
| `side` | `enum` | attio | - |
| `buyer_id` | `record-reference` | key | Organization |
| `seller_id` | `record-reference` | key | Organization |
| `phase` | `enum` | attio | - |
| `assigned_advisor` | `user-reference[]` | key | User |
| `start_date` | `date` | attio | - |
| `expiry_date` | `date` | attio | - |
| `universe_constructed` | `boolean` | attio | - |
| `shortlist_approved` | `boolean` | attio | - |
| `universe_size` | `integer` | both | - |
| `shortlist_size` | `integer` | both | - |
| `tier1_contacted` | `integer` | both | - |
| `responses` | `integer` | both | - |

**Not yet done:** the PostgreSQL `mandates` table (see below) and its
relationships (`mandate_targets`, etc.) still reflect the old two-object
model and have not been updated to match this Attio-side merge — follow-up
work, not part of this change.

## PostgreSQL schema

PostgreSQL stores the CRM mirror, analytical data, automation state, generated documents, scoring outputs, and machine-readable events.

### PostgreSQL functional areas

| Area | Tables | Purpose |
|---|---|---|
| CRM mirror | `users`, `organizations`, `people`, `deals`, `mandates` | Structured copies of core CRM records |
| Business roles | `buyer_roles`, `seller_roles`, `investor_lender_roles` | Buyer, seller, investor, and lender-specific information |
| Activity and pipeline | `activities`, `deal_stage_events`, `signals` | Interactions, deal movements, and market or buyer signals |
| Intelligence and matching | `buyer_intel`, `seller_financials`, `mandate_targets`, `match_scores` | Research, financial normalization, targeting, and opportunity matching |
| Knowledge and documents | `documents`, `vertical_kb`, `graph_edges`, `scorecards` | Generated files, sector research, relationship networks, and reporting |
| Integration operations | `attio_sync_state`, `attio_raw_events` | Synchronization progress and incoming Attio events |
| Scribe integration | `meetings` | Buyer/seller meeting summaries published by the standalone scribe service |

### users

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `attio_id` | `text` | No | PK | - | - |
| `name` | `text` | No | - | - | - |
| `email` | `text` | Yes | - | - | - |
| `access` | `text` | Yes | - | - | - |
| `active` | `boolean` | No | - | - | `true` |
| `raw_attio` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

### organizations

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `attio_id` | `text` | No | PK | - | - |
| `name` | `text` | No | - | - | - |
| `description` | `text` | Yes | - | - | - |
| `type` | `text[]` | No | - | - | `'{}'` |
| `client_type` | `text` | Yes | - | - | - |
| `sector_focus` | `text[]` | No | - | - | `'{}'` |
| `stage_focus` | `text[]` | No | - | - | `'{}'` |
| `geographic_focus` | `text[]` | No | - | - | `'{}'` |
| `hq_country` | `text` | Yes | - | - | - |
| `domains` | `text[]` | No | - | - | `'{}'` |
| `categories` | `text[]` | No | - | - | `'{}'` |
| `relationship_status` | `text` | Yes | - | - | - |
| `connection_strength` | `text` | Yes | - | - | - |
| `owner_attio_id` | `text` | Yes | - | `users.attio_id` | - |
| `last_interaction_at` | `timestamptz` | Yes | - | - | - |
| `raw_attio` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

### people

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `attio_id` | `text` | No | PK | - | - |
| `name` | `text` | No | - | - | - |
| `role` | `text` | Yes | - | - | - |
| `company_attio_id` | `text` | Yes | - | `organizations.attio_id` | - |
| `email` | `text[]` | No | - | - | `'{}'` |
| `linkedin` | `text` | Yes | - | - | - |
| `relationship_status` | `text` | Yes | - | - | - |
| `connection_strength` | `text` | Yes | - | - | - |
| `owner_attio_id` | `text` | Yes | - | `users.attio_id` | - |
| `past_employers` | `jsonb` | No | - | - | `'[]'::jsonb` |
| `education` | `jsonb` | No | - | - | `'[]'::jsonb` |
| `enrichment` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `last_interaction_at` | `timestamptz` | Yes | - | - | - |
| `raw_attio` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

### deals

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `attio_id` | `text` | No | PK | - | - |
| `name` | `text` | No | - | - | - |
| `stage` | `text` | Yes | - | - | - |
| `stage_changed_at` | `timestamptz` | Yes | - | - | - |
| `buyer_organization_attio_id` | `text` | Yes | - | `organizations.attio_id` | - |
| `buyer_person_attio_id` | `text` | Yes | - | `people.attio_id` | - |
| `seller_organization_attio_id` | `text` | Yes | - | `organizations.attio_id` | - |
| `owner_attio_id` | `text` | Yes | - | `users.attio_id` | - |
| `value` | `jsonb` | Yes | - | - | - |
| `teaser_status` | `text` | Yes | - | - | - |
| `nda_count` | `integer` | No | - | - | `0` |
| `cim_ready` | `boolean` | Yes | - | - | - |
| `deal_memo_ready` | `boolean` | Yes | - | - | - |
| `contract_signed_date` | `date` | Yes | - | - | - |
| `exclusivity_date` | `date` | Yes | - | - | - |
| `next_task` | `text` | Yes | - | - | - |
| `data_room_substatus` | `text` | Yes | - | - | - |
| `comparables` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `nda_status` | `text` | Yes | - | - | - |
| `estimated_deal_value_aed` | `numeric` | Yes | - | - | - |
| `expected_close_date` | `date` | Yes | - | - | - |
| `fee` | `numeric` | Yes | - | - | - |
| `assigned_advisor` | `text[]` | No | - | - | `'{}'` |
| `deal_type` | `text` | Yes | - | - | - |
| `universe_constructed` | `boolean` | No | - | - | `false` |
| `universe_size` | `integer` | Yes | - | - | - |
| `shortlist_approved` | `boolean` | No | - | - | `false` |
| `shortlist_size` | `integer` | Yes | - | - | - |
| `tier1_contacted` | `integer` | Yes | - | - | - |
| `responses` | `integer` | Yes | - | - | - |
| `counterparty_interested` | `integer` | Yes | - | - | - |
| `mandate_start_date` | `date` | Yes | - | - | - |
| `mandate_expiry_date` | `date` | Yes | - | - | - |
| `retainer_amount` | `jsonb` | Yes | - | - | - |
| `source_mandate_entry_id` | `text` | Yes | Unique | - | - |
| `raw_attio` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |
| `time_in_stage` | `interval` | Yes | - | - | - |

**Table constraints**

- `CONSTRAINT deals_one_buyer CHECK (`

`deal_type` through `source_mandate_entry_id` merged in from `mandates` below, 2026-08-23 (see the retired Mandate note in the Attio schema section above). `source_mandate_entry_id` is an idempotency key for the migration script, not a business field.

### mandates

Retired 2026-08-23 (see the Attio schema section above) — kept only for its 2 historical rows, nothing writes new rows here going forward.

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `attio_id` | `text` | Yes | Unique | - | - |
| `side` | `text` | No | - | - | - |
| `buyer_attio_id` | `text` | Yes | - | `organizations.attio_id` | - |
| `seller_attio_id` | `text` | Yes | - | `organizations.attio_id` | - |
| `phase` | `text` | Yes | - | - | - |
| `assigned_advisor_attio_ids` | `text[]` | No | - | - | `'{}'` |
| `start_date` | `date` | Yes | - | - | - |
| `expiry_date` | `date` | Yes | - | - | - |
| `universe_constructed` | `boolean` | No | - | - | `false` |
| `shortlist_approved` | `boolean` | No | - | - | `false` |
| `universe_size` | `integer` | Yes | - | - | - |
| `shortlist_size` | `integer` | Yes | - | - | - |
| `tier1_contacted` | `integer` | Yes | - | - | - |
| `responses` | `integer` | Yes | - | - | - |
| `sellers_interested` | `integer` | Yes | - | - | - |
| `retainer_amount` | `jsonb` | Yes | - | - | - |
| `raw_attio` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

### buyer_roles

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `org_attio_id` | `text` | No | Unique | `organizations.attio_id` | - |
| `model` | `text` | Yes | - | - | - |
| `mandate_status` | `text` | Yes | - | - | - |
| `ebitda_floor` | `jsonb` | Yes | - | - | - |
| `check_size_min` | `jsonb` | Yes | - | - | - |
| `check_size_max` | `jsonb` | Yes | - | - | - |
| `ev_ceiling` | `jsonb` | Yes | - | - | - |
| `deal_structure_tolerance` | `text` | Yes | - | - | - |
| `earnout_tolerance` | `boolean` | Yes | - | - | - |
| `profitable_only` | `boolean` | Yes | - | - | - |
| `investment_strategy` | `text` | Yes | - | - | - |
| `notes` | `text` | Yes | - | - | - |
| `key_contact_attio_id` | `text` | Yes | - | `people.attio_id` | - |
| `acquisition_enrichment` | `text` | Yes | - | - | - |
| `deals_introduced` | `integer` | Yes | - | - | - |
| `deals_converted` | `integer` | Yes | - | - | - |
| `ebitda_ceiling` | `jsonb` | Yes | - | - | - |
| `estimated_aum` | `jsonb` | Yes | - | - | - |
| `notable_investments` | `text` | Yes | - | - | - |
| `key_personnel` | `text` | Yes | - | - | - |
| `relationship_warmth` | `text` | Yes | - | - | - |
| `target_geography` | `text[]` | No | - | - | `'{}'` |
| `last_mandate_briefing_date` | `date` | Yes | - | - | - |
| `prior_gcc_acquisition` | `text` | Yes | - | - | - |
| `is_active` | `boolean` | Yes | - | - | - |
| `legacy_entry_id` | `text` | Yes | - | - | - |
| `raw_attio` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

`mandate_details` dropped 2026-08-23 (see `migration-decisions.json`'s `dropped_fields`) — redundant with `investment_strategy` above.

`typical_check_size` dropped 2026-08-23 — redundant with `check_size_min`/`check_size_max` above. SOURCE's `typical_check_size_7` is still read during sync, only to backfill `check_size_min`/`check_size_max` when SOURCE left them blank; it's never written back to a Postgres column.

### seller_roles

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `org_attio_id` | `text` | No | Unique | `organizations.attio_id` | - |
| `outreach_tier` | `text` | Yes | - | - | - |
| `appetite_signal` | `text` | Yes | - | - | - |
| `relationship_status` | `text` | Yes | - | - | - |
| `est_revenue` | `jsonb` | Yes | - | - | - |
| `est_ebitda` | `jsonb` | Yes | - | - | - |
| `owner_salary` | `jsonb` | Yes | - | - | - |
| `valuation_low` | `jsonb` | Yes | - | - | - |
| `valuation_mid` | `jsonb` | Yes | - | - | - |
| `valuation_high` | `jsonb` | Yes | - | - | - |
| `sell_timeline` | `text` | Yes | - | - | - |
| `readiness_score` | `numeric` | Yes | - | - | - |
| `readiness_band` | `text` | Yes | - | - | - |
| `mandate_id` | `uuid` | Yes | - | `mandates.id` | - |
| `last_attempt_date` | `date` | Yes | - | - | - |
| `last_attempt_channel` | `text` | Yes | - | - | - |
| `last_attempt_outcome` | `text` | Yes | - | - | - |
| `lead_quality_score` | `numeric` | Yes | - | - | - |
| `re_engage_date` | `date` | Yes | - | - | - |
| `is_active` | `boolean` | Yes | - | - | - |
| `legacy_entry_id` | `text` | Yes | - | - | - |
| `raw_attio` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

`intake_source` dropped 2026-08-19 — redundant with `organizations.lead_source`, and every populated value was the same constant ("Direct"), so nothing distinguishing was lost. `mandate_id` now only ever points at one of the 2 historical `mandates` rows.

### investor_lender_roles

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `org_attio_id` | `text` | No | - | `organizations.attio_id` | - |
| `investor_type` | `text` | Yes | - | - | - |
| `stage_focus` | `text[]` | No | - | - | `'{}'` |
| `sector_focus` | `text[]` | No | - | - | `'{}'` |
| `interests` | `text` | Yes | - | - | - |
| `facility_type` | `text` | Yes | - | - | - |
| `activity_level` | `text` | Yes | - | - | - |
| `raw_attio` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

**Table constraints**

- `UNIQUE (org_attio_id)`

### activities

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `subject_type` | `text` | No | - | - | - |
| `subject_attio_id` | `text` | Yes | - | - | - |
| `subject_uuid` | `uuid` | Yes | - | - | - |
| `actor_attio_id` | `text` | Yes | - | `users.attio_id` | - |
| `ts` | `timestamptz` | No | - | - | `now()` |
| `channel` | `text` | Yes | - | - | - |
| `direction` | `text` | Yes | - | - | - |
| `outcome` | `text` | Yes | - | - | - |
| `source` | `text` | Yes | - | - | - |
| `payload` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |

**Table constraints**

- `CONSTRAINT activities_subject_present CHECK (`

### deal_stage_events

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `deal_attio_id` | `text` | No | - | `deals.attio_id` | - |
| `from_stage` | `text` | Yes | - | - | - |
| `to_stage` | `text` | No | - | - | - |
| `ts` | `timestamptz` | No | - | - | `now()` |
| `source` | `text` | Yes | - | - | - |
| `created_at` | `timestamptz` | No | - | - | `now()` |

### signals

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `buyer_attio_id` | `text` | No | - | `organizations.attio_id` | - |
| `source` | `text` | No | - | - | - |
| `payload` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `ts` | `timestamptz` | No | - | - | `now()` |
| `rank` | `integer` | Yes | - | - | - |
| `source_cite` | `text` | Yes | - | - | - |
| `created_at` | `timestamptz` | No | - | - | `now()` |

### buyer_intel

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `buyer_attio_id` | `text` | No | - | `organizations.attio_id` | - |
| `cash_window` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `appetite_score` | `numeric` | Yes | - | - | - |
| `brief` | `text` | Yes | - | - | - |
| `ideal_target` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `generated_at` | `timestamptz` | No | - | - | `now()` |
| `created_at` | `timestamptz` | No | - | - | `now()` |

### seller_financials

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `seller_attio_id` | `text` | No | - | `organizations.attio_id` | - |
| `normalised_ebitda_sde` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `add_backs` | `jsonb` | No | - | - | `'[]'::jsonb` |
| `proxy_revenue` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `confidence` | `numeric` | Yes | - | - | - |
| `source_cite` | `jsonb` | No | - | - | `'[]'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

### mandate_targets

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `mandate_id` | `uuid` | No | - | `mandates.id` | - |
| `seller_attio_id` | `text` | No | - | `organizations.attio_id` | - |
| `proxy_size` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `tier` | `text` | Yes | - | - | - |
| `score` | `numeric` | Yes | - | - | - |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

**Table constraints**

- `UNIQUE (mandate_id, seller_attio_id)`

### match_scores

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `buyer_attio_id` | `text` | No | - | `organizations.attio_id` | - |
| `seller_attio_id` | `text` | No | - | `organizations.attio_id` | - |
| `score` | `numeric` | No | - | - | - |
| `dims` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `reasoning` | `text` | Yes | - | - | - |
| `citations` | `jsonb` | No | - | - | `'[]'::jsonb` |
| `generated_at` | `timestamptz` | No | - | - | `now()` |
| `created_at` | `timestamptz` | No | - | - | `now()` |

### documents

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `deal_attio_id` | `text` | No | - | `deals.attio_id` | - |
| `kind` | `text` | No | - | - | - |
| `output_type` | `text` | Yes | - | - | - |
| `drive_ref` | `text` | Yes | - | - | - |
| `extracted_json` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `qc_state` | `text` | Yes | - | - | - |
| `version` | `integer` | No | - | - | `1` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

### vertical_kb

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `sector` | `text` | No | - | - | - |
| `tier1_research` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `source_cite` | `jsonb` | No | - | - | `'[]'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

### graph_edges

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `person_a_attio_id` | `text` | No | - | `people.attio_id` | - |
| `person_b_attio_id` | `text` | No | - | `people.attio_id` | - |
| `hop` | `text` | No | - | - | - |
| `basis` | `text` | Yes | - | - | - |
| `source_cite` | `jsonb` | No | - | - | `'[]'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |

**Table constraints**

- `CONSTRAINT graph_edges_not_self CHECK (person_a_attio_id <> person_b_attio_id)`

### attio_sync_state

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `sync_name` | `text` | No | PK | - | - |
| `last_cursor` | `text` | Yes | - | - | - |
| `last_synced_at` | `timestamptz` | Yes | - | - | - |
| `metadata` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

### attio_raw_events

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | `gen_random_uuid()` |
| `idempotency_key` | `text` | Yes | Unique | - | - |
| `event_type` | `text` | No | - | - | - |
| `payload` | `jsonb` | No | - | - | - |
| `received_at` | `timestamptz` | No | - | - | `now()` |
| `processed_at` | `timestamptz` | Yes | - | - | - |

### scorecards

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `attio_id` | `text` | No | PK | - | - |
| `week_start` | `date` | Yes | - | - | - |
| `created_by_attio_id` | `text` | Yes | - | `users.attio_id` | - |
| `raw_attio` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `updated_at` | `timestamptz` | No | - | - | `now()` |

### meetings

Populated by the standalone scribe service (its own EC2/Postgres, no shared
Alembic chain) via the `scribe_pub` role, which holds `SELECT, INSERT, UPDATE`
on this table and `SELECT` on `organizations`. Not part of the Attio
migration — scribe is the sole writer, Wusool owns the DDL. Canonical
definition: `database/sql/005_meetings.sql`.

| Column | Type | Nullable | Key | References | Default |
|---|---|---:|---|---|---|
| `id` | `uuid` | No | PK | - | - |
| `org_id` | `text` | Yes | - | `organizations.attio_id` | - |
| `org_name_raw` | `text` | Yes | - | - | - |
| `counterparty_role` | `enum (counterparty_role)` | Yes | - | - | - |
| `meeting_type` | `enum (meeting_type)` | Yes | - | - | - |
| `occurred_at` | `timestamptz` | No | - | - | - |
| `title` | `text` | Yes | - | - | - |
| `source` | `enum (meeting_source)` | No | - | - | `'in_house'` |
| `audio_ref` | `text` | Yes | - | - | - |
| `duration_s` | `integer` | Yes | - | - | - |
| `created_by_ref` | `text` | Yes | - | - | - |
| `participants` | `jsonb` | Yes | - | - | - |
| `transcript` | `text` | Yes | - | - | - |
| `summary` | `text` | Yes | - | - | - |
| `metadata` | `jsonb` | No | - | - | `'{}'::jsonb` |
| `created_at` | `timestamptz` | No | - | - | `now()` |
| `scribe_meeting_id` | `uuid` | Yes | Unique | - | - |

## Database indexes

| Index | Table | Definition |
|---|---|---|
| `ix_meetings_org_id` | `meetings` | `org_id` |
| `ix_meetings_occurred_at` | `meetings` | `occurred_at` |

## Data relationships

| From | To | Cardinality / rule |
|---|---|---|
| `organizations.owner_attio_id` | `users.attio_id` | Many-to-one unless constrained unique |
| `people.company_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `people.owner_attio_id` | `users.attio_id` | Many-to-one unless constrained unique |
| `deals.buyer_organization_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `deals.buyer_person_attio_id` | `people.attio_id` | Many-to-one unless constrained unique |
| `deals.seller_organization_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `deals.owner_attio_id` | `users.attio_id` | Many-to-one unless constrained unique |
| `mandates.buyer_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `mandates.seller_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `buyer_roles.org_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `buyer_roles.key_contact_attio_id` | `people.attio_id` | Many-to-one unless constrained unique |
| `seller_roles.org_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `seller_roles.mandate_id` | `mandates.id` | Many-to-one unless constrained unique |
| `investor_lender_roles.org_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `activities.actor_attio_id` | `users.attio_id` | Many-to-one unless constrained unique |
| `deal_stage_events.deal_attio_id` | `deals.attio_id` | Many-to-one unless constrained unique |
| `signals.buyer_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `buyer_intel.buyer_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `seller_financials.seller_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `mandate_targets.mandate_id` | `mandates.id` | Many-to-one unless constrained unique |
| `mandate_targets.seller_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `match_scores.buyer_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `match_scores.seller_attio_id` | `organizations.attio_id` | Many-to-one unless constrained unique |
| `documents.deal_attio_id` | `deals.attio_id` | Many-to-one unless constrained unique |
| `graph_edges.person_a_attio_id` | `people.attio_id` | Many-to-one unless constrained unique |
| `graph_edges.person_b_attio_id` | `people.attio_id` | Many-to-one unless constrained unique |
| `scorecards.created_by_attio_id` | `users.attio_id` | Many-to-one unless constrained unique |
| `meetings.org_id` | `organizations.attio_id` | Many-to-one; nullable, enforced via `fk_meetings_org` when set |

Notable rules:

- `deals` allows either an organization buyer or a person buyer, but not both.
- Role tables are one-to-one with an organization because `org_attio_id` is unique.
- `mandate_targets` is unique per `(mandate_id, seller_attio_id)` pair.
- `graph_edges` rejects self-referencing person edges.
- `meetings.org_id` is nullable — `org_name_raw` is set instead when scribe
  cannot resolve an organization at publish time. When `org_id` is set, it
  must reference an existing `organizations.attio_id` row (`fk_meetings_org`,
  enabled 2026-08-11).

## Data ownership

| Responsibility | Description |
|---|---|
| Attio | Business-managed CRM and relationship data |
| PostgreSQL | Platform, enrichment, analytical, and automation data |
| Shared | Operational data synchronized between both platforms |
| Key | Record identifiers and relationship references |

## Summary

The combined model provides a unified structure for organizations, people, deals, mandates, investor and seller workflows, activities, intelligence, matching, documents, and integrations.
