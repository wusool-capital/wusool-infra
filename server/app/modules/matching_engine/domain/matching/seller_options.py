"""The select options of the seller-role fields a criterion can be matched on.

Copied from `ddl_commands.api.sellers.SELLER_ROLE_FIELDS`, whose `api` layer this
`domain/` can't import; `tests/test_seller_select_vocabulary.py` catches drift.
"""

SELLER_SELECT_OPTIONS: dict[str, tuple[str, ...]] = {
    "outreach_tier": ("Archive", "Tier 1", "Tier 2", "Tier 3"),
    "appetite_signal": (
        "Expressed Interest Directly / Inbound Deal",
        "Listed on Business-for-Sale Platform",
        "No Signal",
        "Warm Introduction / Direct Outreach",
    ),
    "relationship_status": (
        "Not Contacted",
        "Outreach Sent",
        "Positive Response",
        "Not Now",
        "No Response",
        "Referred Out",
        "Converted to Mandate",
    ),
}
