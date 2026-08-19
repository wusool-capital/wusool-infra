"""Which `buyer_roles` fields `/edit-buyer` may edit, and how. See
`ddl_commands/shared/organization_field_spec.py` for the same idea applied
to `organizations`.

Deliberately excluded (plan.md Part C): `acquisition_enrichment`,
`deals_introduced`, `deals_converted` (ownership: both manual and
pipeline-written — needs the data engineer's confirmation before this bot
edits them). `key_contact` deferred — a `record-reference` type, not a
plain field. No gated fields on the buyer side — nor on the seller side
any more, since `intake_source` was dropped in #53.
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
    FieldSpec("ebitda_floor", "EBITDA floor (AED)", "currency"),
    FieldSpec("check_size_min", "Check size - min (AED)", "currency"),
    FieldSpec("check_size_max", "Check size - max (AED)", "currency"),
    FieldSpec("ev_ceiling", "EV ceiling (AED)", "currency"),
)

BUYER_ROLE_FIELDS_BY_NAME = {f.name: f for f in BUYER_ROLE_FIELDS}
GATED_BUYER_ROLE_FIELDS: frozenset[str] = frozenset()
