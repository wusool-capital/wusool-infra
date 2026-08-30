# `wusool_crm` Postgres schema reference

Generated from `wusool_db/models/*.py` (2026-08-29) — that package is the
source Alembic's `--autogenerate` diffs against, so it is the closest thing
this repo has to a single source of truth for the schema. Current Alembic
head: **`d5080e26bfc2`** (`drop_deals_next_task`).

**Two tiers of confidence — read this before trusting any table below:**

- **Confirmed** tables were mapped from a real, applied DDL history (Stage
  1-3 of the Alembic migration, or a hand-written migration in this repo) and
  are not flagged as drafts anywhere in their source file.
- **Static-analysis draft** tables (13, marked below) were derived by reading
  `database/sql/00*.sql` end-to-end, *not* from a live-database reflection —
  see `wusool_db/models/_static_analysis_notice.py` for the full caveat.
  Whoever runs the still-pending "Stage 4" live-DB reflection must diff each
  one against a real `psql \d` / `sqlalchemy.inspect()` before trusting it for
  `alembic stamp head`. Two columns in this tier (`buyer_intel.brief_embedding`,
  `vertical_kb.embedding`) are additionally conditional on the `vector`
  Postgres extension being installed — confirm before relying on them.

Money-shaped JSONB columns (marked below) hold either `{"amount": ...,
"currency": ...}` or `NULL` — never a fabricated value when Attio has none.

---

## Confirmed tables

### `organizations` (`organization.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| attio_id | text | no | | PK |
| name | text | no | | |
| description | text | yes | | |
| type | text[] | no | `{}` | GIN index |
| client_type | text | yes | | |
| sector_focus | text[] | no | `{}` | |
| stage_focus | text[] | no | `{}` | |
| geographic_focus | text[] | no | `{}` | |
| hq_country | text | yes | | |
| domains | text[] | no | `{}` | GIN index |
| categories | text[] | no | `{}` | |
| relationship_status | text | yes | | |
| connection_strength | text | yes | | |
| owner_attio_id | text | yes | | FK → users.attio_id |
| last_interaction_at | timestamptz | yes | | |
| estimated_arr | text | yes | | |
| funding_raised | jsonb | yes | | money-shaped |
| removed_at | timestamptz | yes | | Attio-owned soft-delete marker |
| angellist / facebook / instagram / twitter | text | yes | | |
| twitter_follower_count | integer | yes | | |
| foundation_date | date | yes | | |
| ticket_size | text | yes | | |
| lead_source | text | yes | | |
| employee_range | text | yes | | SOURCE's own bands, e.g. `1-10`, `100K+` |
| linkedin | text | yes | | |
| logo_url | text | yes | | |
| is_active | boolean | yes | | true = current record in a duplicate-name group |
| raw_attio | jsonb | no | `{}` | |
| created_at / updated_at | timestamptz | no | `now()` | |

Indexes: GIN trigram on `name` (`ix_organizations_name_trgm`).

### `person` (`person.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| attio_id | text | no | | PK |
| name | text | no | | |
| role | text | yes | | |
| company_attio_id | text | yes | | FK → organizations.attio_id, indexed |
| email | text[] | no | `{}` | GIN index |
| linkedin | text | yes | | |
| relationship_status | text | yes | | |
| connection_strength | text | yes | | |
| owner_attio_id | text | yes | | FK → users.attio_id |
| past_employers | jsonb | no | `[]` | |
| education | jsonb | no | `[]` | |
| enrichment | jsonb | no | `{}` | |
| last_interaction_at | timestamptz | yes | | |
| job_title / contact_type / phone / avatar_url | text | yes | | |
| angellist / facebook / instagram / twitter | text | yes | | |
| twitter_follower_count | integer | yes | | |
| removed_at | timestamptz | yes | | soft-delete (FKs use ON DELETE NO ACTION) |
| raw_attio | jsonb | no | `{}` | |
| created_at / updated_at | timestamptz | no | `now()` | |

### `deals` (`deal.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| attio_id | text | no | | PK |
| name | text | no | | |
| stage | text | yes | | indexed |
| stage_changed_at | timestamptz | yes | | indexed (DESC) |
| buyer_organization_attio_id | text | yes | | FK → organizations, indexed |
| buyer_person_attio_id | text | yes | | FK → person |
| seller_organization_attio_id | text | yes | | FK → organizations, indexed |
| owner_attio_id | text | yes | | FK → users.attio_id |
| value | jsonb | yes | | money-shaped |
| teaser_status | text | yes | | |
| nda_count | integer | no | `0` | |
| cim_ready / deal_memo_ready | boolean | yes | | real NULLs exist |
| contract_signed_date / exclusivity_date | date | yes | | |
| data_room_substatus | text | yes | | |
| comparables | jsonb | no | `{}` | |
| nda_status | text | yes | | |
| estimated_deal_value_usd | numeric | yes | | renamed from `_aed` 2026-08-25 |
| expected_close_date | date | yes | | |
| fee | numeric | yes | | plain scalar, not money-shaped |
| assigned_advisor | text[] | no | `{}` | multiselect of advisor names |
| deal_type | text | yes | | e.g. Sell-side/Buy-side |
| universe_constructed | boolean | no | `false` | |
| universe_size | integer | yes | | |
| shortlist_approved | boolean | no | `false` | |
| shortlist_size / tier1_contacted / responses | integer | yes | | |
| counterparty_interested | integer | yes | | |
| mandate_start_date / mandate_expiry_date | date | yes | | |
| retainer_amount | jsonb | yes | | money-shaped |
| source_mandate_entry_id | text | yes | unique | idempotency key, mandate→deal migration |
| raw_attio | jsonb | no | `{}` | |
| created_at / updated_at | timestamptz | no | `now()` | |
| time_in_stage | interval | yes | | |

Constraint: `deals_one_buyer` — `buyer_organization_attio_id IS NULL OR buyer_person_attio_id IS NULL`.

### `buyer_roles` (`buyer_role.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| org_attio_id | text | no | | FK → organizations, ON DELETE CASCADE, indexed (no longer unique as of 2026-08-28) |
| model / mandate_status | text | yes | | |
| ebitda_floor / check_size_min / check_size_max / ev_ceiling | jsonb | yes | | money-shaped |
| deal_structure_tolerance | text | yes | | |
| earnout_tolerance / profitable_only | boolean | yes | | |
| investment_strategy | text | yes | | |
| notes | text | yes | | legacy free-text notes field |
| key_contact_attio_id | text | yes | | FK → person.attio_id |
| acquisition_enrichment | text | yes | | |
| deals_introduced / deals_converted | integer | yes | | |
| ebitda_ceiling / estimated_aum | jsonb | yes | | money-shaped |
| notable_investments / key_personnel / relationship_warmth | text | yes | | |
| target_geography | text[] | no | `{}` | multiselect |
| last_mandate_briefing_date | date | yes | | |
| prior_gcc_acquisition | text | yes | | |
| is_active | boolean | yes | | current vs. stale duplicate |
| legacy_entry_id | text | yes | unique | one row per DEV Attio entry |
| raw_attio | jsonb | no | `{}` | |
| created_at / updated_at | timestamptz | no | `now()` | |

### `seller_roles` (`seller_role.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| org_attio_id | text | no | | FK → organizations, ON DELETE CASCADE, indexed (no longer unique) |
| outreach_tier / appetite_signal / relationship_status | text | yes | | |
| est_revenue / est_ebitda / owner_salary / valuation_low / valuation_mid / valuation_high | jsonb | yes | | money-shaped |
| sell_timeline | text | yes | | |
| readiness_score | numeric | yes | | |
| readiness_band | text | yes | | |
| last_attempt_date | date | yes | | |
| last_attempt_channel / last_attempt_outcome | text | yes | | |
| lead_quality_score | numeric | yes | | |
| re_engage_date | date | yes | | |
| is_active | boolean | yes | | current vs. stale duplicate |
| legacy_entry_id | text | yes | unique | one row per DEV Attio entry |
| years_active | integer | yes | | Lead Magnet field |
| funding_stage | text | yes | | Lead Magnet field |
| revenue_last_full_year / revenue_year_before / annual_rent_cost | jsonb | yes | | money-shaped, Lead Magnet |
| gross_margin_pct | numeric | yes | | Lead Magnet |
| ebitda_deducts_salary | boolean | yes | | Lead Magnet |
| largest_customer_revenue_pct / repeat_revenue_pct | numeric | yes | | Lead Magnet |
| location_count | integer | yes | | Lead Magnet |
| raw_attio | jsonb | no | `{}` | |
| created_at / updated_at | timestamptz | no | `now()` | |

### `notes` (`note.py`) — new, 2026-08-28/29

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| organization_id | text | **yes** (2026-08-29) | | FK → organizations.attio_id; indexed. Blank only when the note's sole anchor (a person or role) has no org at all |
| person_id | text | yes | | FK → person.attio_id; indexed |
| buyer_role_id | uuid | yes | | FK → buyer_roles.id |
| seller_role_id | uuid | yes | | FK → seller_roles.id |
| note_type | text | no | | CHECK: `Manual` or `Meeting` |
| content | text | no | | |
| created_at | timestamptz | no | `now()` | |

Populated by `workflows/crm-sync/scripts/source-attio/backfill-notes.ps1`
from SOURCE Attio's `note` custom object, via a not-yet-built
`database/sync-notes-from-source.ps1`. Replaces the notes fields formerly
scattered across `organizations`/`person`/`buyer_roles`.

### `meetings` (`meeting.py`)

Owned by Scribe (its own standalone Postgres/Alembic chain) — read-only from
this repo's perspective. DDL: `database/sql/005_meetings.sql`.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | | PK |
| org_id | text | yes | | FK → organizations, indexed |
| org_name_raw | text | yes | | |
| counterparty_role | enum(`buyer`,`seller`) | yes | | native Postgres enum |
| meeting_type | enum(`enrichment`,`alignment`,`owner_iv`,`buyer_intro`,`internal`) | yes | | native Postgres enum |
| occurred_at | timestamptz | no | | indexed |
| title | text | yes | | |
| source | enum(`in_house`,`granola`,`manual`) | no | `in_house` | native Postgres enum |
| audio_ref | text | yes | | |
| duration_s | integer | yes | | |
| created_by_ref | text | yes | | |
| participants | jsonb | yes | | |
| transcript / summary | text | yes | | |
| metadata (attr: `metadata_`) | jsonb | no | `{}` | |
| created_at | timestamptz | no | `now()` | |
| scribe_meeting_id | uuid | yes | unique | |

### `match_scores` (`match_score.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| buyer_attio_id / seller_attio_id | text | no | | FK → organizations, ON DELETE CASCADE; composite index with `generated_at DESC` |
| score | numeric | no | | |
| dims | jsonb | no | `{}` | |
| reasoning | text | yes | | |
| citations | jsonb | no | `[]` | |
| generated_at / created_at | timestamptz | no | `now()` | |

### `match_results` (`match_result.py`)

One table covering run audit + shortlisted results + approval. Rows come in
two kinds distinguished by `rank`: `rank IS NULL` is the one-per-`run_id`
header row (run-level columns meaningful); `rank IS NOT NULL` is a
shortlisted candidate row (candidate-level columns meaningful).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| run_id | uuid | no | | indexed |
| buyer_attio_id | text | no | | FK → organizations, CASCADE |
| buyer_role_id | uuid | no | | FK → buyer_roles, CASCADE; indexed |
| rank | integer | yes | | NULL ⇒ header row |
| seller_attio_id | text | yes | | FK → organizations, CASCADE (candidate rows) |
| seller_role_id | uuid | yes | | FK → seller_roles, CASCADE |
| match_score_id | uuid | yes | | FK → match_scores.id |
| match_score / data_confidence | numeric | yes | | |
| why_chosen_over_alternatives / recommended_pitch / risks_and_gaps | text | yes | | |
| status | text | no | `GENERATED` | CHECK: GENERATED/PENDING_REVIEW/APPROVED/REJECTED/FAILED; indexed |
| approved_by | text | yes | | |
| decision | text | yes | | CHECK: APPROVED/REJECTED |
| decided_at | timestamptz | yes | | |
| decision_notes | text | yes | | |
| requested_by / model_version | text | yes | | header-row only |
| requirement_profile_version | integer | yes | | header-row only |
| requirement_profile | jsonb | yes | | header-row only |
| candidates_considered / candidates_filtered | integer | yes | | header-row only |
| filters_skipped | jsonb | no | `[]` | header-row only |
| vector_queries | jsonb | yes | | header-row only, always NULL in Branch 1 |
| final_candidate_ids | jsonb | yes | | header-row only |
| execution_duration_ms | integer | yes | | header-row only |
| errors | jsonb | yes | | header-row only |
| started_at | timestamptz | no | `now()` | header-row only |
| completed_at | timestamptz | yes | | header-row only |
| metadata (attr: `metadata_`) | jsonb | no | `{}` | unstructured, unused so far |
| created_at | timestamptz | no | `now()` | |

Constraint: `uq_match_results_run_header` — unique `run_id` where `rank IS NULL`.

---

## Static-analysis draft tables

Derived from `database/sql/00*.sql` end-to-end, not a live reflection — see
`wusool_db/models/_static_analysis_notice.py`. Confirm each against a real
`psql \d` before relying on it for `alembic stamp head`.

### `users` (`user.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| attio_id | text | no | | PK |
| name | text | no | | |
| email / access | text | yes | | |
| active | boolean | no | `true` | |
| raw_attio | jsonb | no | `{}` | |
| created_at / updated_at | timestamptz | no | `now()` | |

### `investor_lender_roles` (`investor_lender_role.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| org_attio_id | text | no | | FK → organizations, CASCADE, unique (one row per org) |
| investor_type | text | yes | | |
| stage_focus / sector_focus | text[] | no | `{}` | |
| interests / facility_type / activity_level | text | yes | | |
| raw_attio | jsonb | no | `{}` | |
| created_at / updated_at | timestamptz | no | `now()` | |

### `activities` (`activity.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| subject_type | text | no | | |
| subject_attio_id | text | yes | | polymorphic ref, no FK |
| subject_uuid | uuid | yes | | polymorphic ref, no FK |
| actor_attio_id | text | yes | | FK → users.attio_id |
| ts | timestamptz | no | `now()` | indexed DESC |
| channel / direction / outcome / source | text | yes | | |
| payload | jsonb | no | `{}` | |
| created_at | timestamptz | no | `now()` | |

Constraint: `activities_subject_present` — `subject_attio_id IS NOT NULL OR subject_uuid IS NOT NULL`. Indexed on `(subject_type, subject_attio_id)`.

### `deal_stage_events` (`deal_stage_event.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| deal_attio_id | text | no | | FK → deals, CASCADE |
| from_stage | text | yes | | |
| to_stage | text | no | | |
| ts | timestamptz | no | `now()` | |
| source | text | yes | | |
| created_at | timestamptz | no | `now()` | |

Indexed on `(deal_attio_id, ts DESC)`.

### `signals` (`signal.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| buyer_attio_id | text | no | | FK → organizations, CASCADE |
| source | text | no | | |
| payload | jsonb | no | `{}` | |
| ts | timestamptz | no | `now()` | |
| rank | integer | yes | | |
| source_cite | text | yes | | |
| created_at | timestamptz | no | `now()` | |

Indexed on `(buyer_attio_id, ts DESC)`.

### `buyer_intel` (`buyer_intel.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| buyer_attio_id | text | no | | FK → organizations, CASCADE |
| cash_window | jsonb | no | `{}` | |
| appetite_score | numeric | yes | | |
| brief | text | yes | | |
| ideal_target | jsonb | no | `{}` | |
| generated_at / created_at | timestamptz | no | `now()` | |
| brief_embedding | vector(1536) | yes | | **conditional on `vector` extension** |

Indexed on `(buyer_attio_id, generated_at DESC)`.

### `seller_financials` (`seller_financial.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| seller_attio_id | text | no | | FK → organizations, CASCADE, indexed |
| normalised_ebitda_sde | jsonb | no | `{}` | |
| add_backs | jsonb | no | `[]` | |
| proxy_revenue | jsonb | no | `{}` | |
| confidence | numeric | yes | | |
| source_cite | jsonb | no | `[]` | |
| created_at / updated_at | timestamptz | no | `now()` | |

### `documents` (`document.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| deal_attio_id | text | no | | FK → deals, CASCADE; composite index with `kind` |
| kind | text | no | | |
| output_type / drive_ref | text | yes | | |
| extracted_json | jsonb | no | `{}` | |
| qc_state | text | yes | | |
| version | integer | no | `1` | |
| created_at / updated_at | timestamptz | no | `now()` | |

### `graph_edges` (`graph_edge.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| person_a_attio_id / person_b_attio_id | text | no | | FK → person, CASCADE; composite index |
| hop | text | no | | |
| basis | text | yes | | |
| source_cite | jsonb | no | `[]` | |
| created_at | timestamptz | no | `now()` | |

Constraint: `graph_edges_not_self` — `person_a_attio_id <> person_b_attio_id`.

### `attio_sync_state` (`attio_sync_state.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| sync_name | text | no | | PK |
| last_cursor | text | yes | | |
| last_synced_at | timestamptz | yes | | |
| metadata (attr: `metadata_`) | jsonb | no | `{}` | |
| updated_at | timestamptz | no | `now()` | **no `created_at` column at all** |

### `attio_raw_events` (`attio_raw_event.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| idempotency_key | text | yes | unique | |
| event_type | text | no | | |
| payload | jsonb | **no** | **none** | unlike every other jsonb column here, no server default — literal read of the DDL |
| received_at | timestamptz | no | `now()` | |
| processed_at | timestamptz | yes | | |

### `scorecards` (`scorecard.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| attio_id | text | no | | PK |
| week_start | date | yes | | indexed DESC |
| created_by_attio_id | text | yes | | FK → users.attio_id |
| raw_attio | jsonb | no | `{}` | |
| created_at / updated_at | timestamptz | no | `now()` | |

### `vertical_kb` (`vertical_kb.py`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | no | `gen_random_uuid()` | PK |
| sector | text | no | | indexed |
| tier1_research | jsonb | no | `{}` | |
| source_cite | jsonb | no | `[]` | |
| created_at / updated_at | timestamptz | no | `now()` | |
| embedding | vector(1536) | yes | | **conditional on `vector` extension** |

---

## Not mapped in this repo

- `mandate_targets` — table existed historically but the Mandates list was
  fully retired 2026-08-23 (merged into `deals`); no current model.
