"""Which `seller_roles` fields `/edit-seller` may edit, and how. See
`ddl_commands/shared/organization_field_spec.py` for the same idea applied
to `organizations`.

Deliberately excluded (plan.md Part C): `readiness_band` (zero options
currently defined in DEV Attio — nothing to show in a dropdown),
`readiness_score`/`lead_quality_score` (ownership: both manual and
pipeline-written — needs the data engineer's confirmation before this bot
edits them, not this bot's own call). `intake_source` was dropped from the
table entirely (#53 — every populated value was the constant "Direct", and
`organizations.lead_source` already carries the signal), taking the only
gated field with it: `GATED_SELLER_ROLE_FIELDS` is empty now, and the
confirmation-checkbox machinery it drove is kept for the next write-once
field rather than deleted.
"""

from ddl_commands.shared.organization_field_spec import FieldSpec

SELLER_ROLE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "outreach_tier",
        "Outreach tier",
        "select",
        options=("Archive", "Tier 1", "Tier 2", "Tier 3"),
    ),
    FieldSpec(
        "appetite_signal",
        "Appetite signal",
        "select",
        options=(
            "Expressed Interest Directly / Inbound Deal",
            "Listed on Business-for-Sale Platform",
            "No Signal",
            "Warm Introduction / Direct Outreach",
        ),
    ),
    FieldSpec(
        "relationship_status",
        "Relationship status",
        "select",
        options=(
            "Not Contacted",
            "Outreach Sent",
            "Positive Response",
            "Not Now",
            "No Response",
            "Referred Out",
            "Converted to Mandate",
        ),
    ),
    FieldSpec(
        "sell_timeline",
        "Sell timeline",
        "select",
        options=("Immediate", "Within 6 Months", "6-12 Months", "12-24 Months", "Not Selling"),
    ),
    FieldSpec("last_attempt_date", "Last attempt date", "date"),
    FieldSpec(
        "last_attempt_channel",
        "Last attempt channel",
        "select",
        options=("Email", "In Person", "Instagram DM", "LinkedIn InMail", "Phone"),
    ),
    FieldSpec(
        "last_attempt_outcome",
        "Last attempt outcome",
        "select",
        options=(
            "No Response",
            "Not Now",
            "Referred",
            "Responded Negatively",
            "Responded Positively",
        ),
    ),
    FieldSpec("re_engage_date", "Re-engage date", "date"),
    FieldSpec("est_revenue", "Est. revenue (USD)", "currency"),
    FieldSpec("est_ebitda", "Est. EBITDA (USD)", "currency"),
    FieldSpec("owner_salary", "Owner salary (USD)", "currency"),
    FieldSpec("valuation_low", "Valuation - low (USD)", "currency"),
    FieldSpec("valuation_mid", "Valuation - mid (USD)", "currency"),
    FieldSpec("valuation_high", "Valuation - high (USD)", "currency"),
)

SELLER_ROLE_FIELDS_BY_NAME = {f.name: f for f in SELLER_ROLE_FIELDS}
GATED_SELLER_ROLE_FIELDS: frozenset[str] = frozenset()
