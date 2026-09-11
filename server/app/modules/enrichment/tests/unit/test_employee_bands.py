import pytest

from app.modules.enrichment.domain.employee_bands import bucket_employee_count


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, None),
        (1, "1-10"),
        (10, "1-10"),
        (11, "11-50"),
        (250, "51-250"),
        (251, "251-1K"),
        (1_000, "251-1K"),
        (1_001, "1K-5K"),
        (100_000, "50K-100K"),
        (100_001, "100K+"),
        (5_000_000, "100K+"),
    ],
)
def test_bucket_employee_count(count: int, expected: str | None) -> None:
    assert bucket_employee_count(count) == expected
