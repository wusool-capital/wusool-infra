import pytest
from pydantic import ValidationError

from app.modules.interactions.config import InteractionsSettings
from app.modules.interactions.domain.model import ScoringRules


def test_defaults_are_the_plans_starting_values_and_ingest_is_off() -> None:
    settings = InteractionsSettings()

    assert settings.interactions_enabled is False
    assert settings.scoring_rules() == ScoringRules()
    assert settings.mailboxes == ("jules@wusoolcapital.com", "ramzy@wusoolcapital.com")
    assert settings.internal_domains == ("wusoolcapital.com", "dopaminecap.com")


def test_mailboxes_are_normalised() -> None:
    settings = InteractionsSettings(interactions_mailboxes="Jules@WusoolCapital.com  hugo@x.com")

    assert settings.mailboxes == ("jules@wusoolcapital.com", "hugo@x.com")


def test_a_bad_mailbox_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InteractionsSettings(interactions_mailboxes="jules@wusoolcapital.com not-an-address")


def test_tuned_values_reach_the_scoring_rules() -> None:
    settings = InteractionsSettings(
        interactions_meeting_points=5, interactions_label_cutoffs="2 4 8 16"
    )

    rules = settings.scoring_rules()
    assert rules.meeting_points == 5
    assert rules.cutoffs == (2.0, 4.0, 8.0, 16.0)


@pytest.mark.parametrize("cutoffs", ["1 3 7", "1 3 7 15 30", "15 7 3 1", "a b c d"])
def test_label_cutoffs_need_four_ascending_numbers(cutoffs: str) -> None:
    with pytest.raises(ValidationError):
        InteractionsSettings(interactions_label_cutoffs=cutoffs)
