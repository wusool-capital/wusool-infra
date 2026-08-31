"""Which `buyer_roles` fields `/edit-buyer` may edit, and how. See
`ddl_commands/shared/organization_field_spec.py` for the same idea applied
to `organizations`.

Deliberately excluded (plan.md Part C): `acquisition_enrichment`,
`deals_introduced`, `deals_converted` (ownership: both manual and
pipeline-written — needs the data engineer's confirmation before this bot
edits them). `key_contact` deferred — a `record-reference` type, not a
plain field. `key_personnel` — intentionally not exposed. No gated fields
on the buyer side — nor on the seller side any more, since `intake_source`
was dropped in #53.

Attribute types verified live against the DEV Attio workspace (2026-08-30)
via `GET /v2/lists/buyer_role/attributes`: `prior_gcc_acquisition` is
genuinely free text, while `relationship_warmth` is a `select` and carries
Attio's own two options below. It had been guessed as `"text"`, which fails
the Attio write with a 400 once an operator fills it in.
"""

from ddl_commands.shared.organization_field_spec import FieldSpec

BUYER_ROLE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "model", "Model", "select", options=("Model 1 (Network)", "Model 2 (Full Mandate)")
    ),
    FieldSpec(
        "mandate_status",
        "Mandate status",
        "select",
        options=("Active", "Paused", "Completed", "Dormant"),
    ),
    FieldSpec(
        "deal_structure_tolerance",
        "Deal structure tolerance",
        "select",
        options=("Majority", "Minority", "Flexible", "Acquisition Financing"),
    ),
    FieldSpec("earnout_tolerance", "Earnout tolerance", "bool"),
    FieldSpec("profitable_only", "Profitable only", "bool"),
    FieldSpec("investment_strategy", "Investment strategy", "multiline"),
    FieldSpec("notes", "Notes", "multiline"),
    FieldSpec("ebitda_floor", "EBITDA floor (USD)", "currency"),
    FieldSpec("check_size_min", "Check size - min (USD)", "currency"),
    FieldSpec("check_size_max", "Check size - max (USD)", "currency"),
    FieldSpec("ev_ceiling", "EV ceiling (USD)", "currency"),
    FieldSpec("ebitda_ceiling", "EBITDA ceiling (USD)", "currency"),
    FieldSpec("estimated_aum", "Estimated AUM (USD)", "currency"),
    FieldSpec("notable_investments", "Notable investments", "multiline"),
    FieldSpec("relationship_warmth", "Relationship warmth", "select", options=("Warm", "Cold")),
    FieldSpec(
        "target_geography", "Target geography (comma-separated)", "multi_select_text"
    ),
    FieldSpec("last_mandate_briefing_date", "Last mandate briefing date", "date"),
    FieldSpec("prior_gcc_acquisition", "Prior GCC acquisition", "text"),
)

BUYER_ROLE_FIELDS_BY_NAME = {f.name: f for f in BUYER_ROLE_FIELDS}
GATED_BUYER_ROLE_FIELDS: frozenset[str] = frozenset()
