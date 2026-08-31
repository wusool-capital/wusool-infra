from datetime import date

from ddl_commands.shared.organization_schemas import OrganizationUpdate


def test_everything_optional() -> None:
    validated = OrganizationUpdate.model_validate({})
    assert validated.description is None
    assert validated.linkedin is None


def test_newer_fields_round_trip() -> None:
    validated = OrganizationUpdate.model_validate(
        {
            "linkedin": "https://linkedin.com/company/acme",
            "logo_url": "https://acme.example/logo.png",
            "angellist": "acme",
            "facebook": "acme",
            "instagram": "acme",
            "twitter": "acme",
            "twitter_follower_count": 1200,
            "foundation_date": date(2010, 1, 1),
            "ticket_size": "$1M-$10M",
            "lead_source": "Referral",
            "employee_range": "11-50",
        }
    )
    assert validated.twitter_follower_count == 1200
    assert isinstance(validated.twitter_follower_count, int)
    assert validated.foundation_date == date(2010, 1, 1)
    assert validated.ticket_size == "$1M-$10M"
    assert validated.lead_source == "Referral"
    assert validated.employee_range == "11-50"
