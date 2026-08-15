import pytest
from pydantic import ValidationError

from ddl_commands.modules.buyers.schemas import BuyerUpdate


def test_collects_all_field_errors_not_fail_fast() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BuyerUpdate.model_validate(
            {
                "deals_introduced": -1,  # under the 0 floor
                "ebitda_floor": {"amount": 100, "currency": "usd"},  # lowercase, invalid
            }
        )

    locs = {tuple(e["loc"]) for e in exc_info.value.errors()}
    assert ("deals_introduced",) in locs
    assert ("ebitda_floor", "currency") in locs


def test_valid_input_round_trips() -> None:
    validated = BuyerUpdate.model_validate(
        {
            "model": "Buy-and-build",
            "profitable_only": True,
            "ebitda_floor": {"amount": 5_000_000, "currency": "AED"},
        }
    )
    assert validated.model == "Buy-and-build"
    assert validated.profitable_only is True
    assert validated.ebitda_floor is not None
    assert validated.ebitda_floor.currency == "AED"


def test_everything_optional() -> None:
    validated = BuyerUpdate.model_validate({})
    assert validated.model is None
    assert validated.profitable_only is None
