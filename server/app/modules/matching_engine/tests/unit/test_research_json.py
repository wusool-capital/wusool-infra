from datetime import UTC, date, datetime

from app.modules.matching_engine.domain.matching.research import (
    ResearchField,
    ResearchLinkedIn,
    ResearchPost,
    ResearchRecord,
)
from app.modules.matching_engine.persistence.research_json import (
    research_from_dict,
    research_to_dict,
)


def test_research_round_trips_through_its_stored_json() -> None:
    record = ResearchRecord(
        claimed_at=datetime(2026, 11, 4, 6, 0, tzinfo=UTC),
        outcome="done",
        fields=(
            ResearchField("sector_focus", "organization", ["Clinic"], "Clinic", 0.9, "u", "r"),
            ResearchField(
                "funding_raised",
                "organization",
                {"amount": 2_000_000, "currency": "USD"},
                "USD 2,000,000",
                0.7,
                "u",
                "r",
            ),
            ResearchField(
                "foundation_date", "organization", date(2001, 1, 1).isoformat(), "", 1, "u", "r"
            ),
        ),
        linkedin=ResearchLinkedIn(
            outcome="completed",
            posts=(ResearchPost("https://li/1", "Hi", "Ann", datetime(2026, 11, 1, tzinfo=UTC)),),
        ),
        saved_fields=("sector_focus",),
    )

    assert research_from_dict(research_to_dict(record)) == record


def test_unreadable_stored_research_is_ignored() -> None:
    assert research_from_dict({"claimed_at": "not a date"}) is None
    assert research_from_dict(None) is None
