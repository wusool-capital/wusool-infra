"""Buckets a raw employee count into one of Attio's fixed `employee_range`
option labels. Declared here rather than imported from `ddl_commands` (this
module must never import it — see the package docstring) — these band
boundaries mirror `ddl_commands.api.organizations.ORGANIZATION_FIELDS`'s
`employee_range` options, which are Attio's own fixed vocabulary and change
about as often as the `FieldKind` literals already duplicated the same way.
`EMPLOYEE_RANGE_OPTIONS` is that same vocabulary, in order — used to constrain
the LLM extraction prompt for the one path (`_research_and_extract`) that
doesn't already go through `bucket_employee_count`.
"""

_BANDS: tuple[tuple[int, int | None, str], ...] = (
    (1, 10, "1-10"),
    (11, 50, "11-50"),
    (51, 250, "51-250"),
    (251, 1_000, "251-1K"),
    (1_001, 5_000, "1K-5K"),
    (5_001, 10_000, "5K-10K"),
    (10_001, 50_000, "10K-50K"),
    (50_001, 100_000, "50K-100K"),
    (100_001, None, "100K+"),
)

EMPLOYEE_RANGE_OPTIONS: tuple[str, ...] = tuple(label for _, _, label in _BANDS)


def bucket_employee_count(count: int) -> str | None:
    if count < 1:
        return None
    for low, high, label in _BANDS:
        if count >= low and (high is None or count <= high):
            return label
    return None
