import pytest
from pydantic import ValidationError

from ddl_commands.modules.buyers.schemas import BuyerUpdate


def test_collects_all_field_errors_not_fail_fast() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BuyerUpdate.model_validate(
            {
                "model": "x" * 101,  # over max_length=100
                "notes": "y" * 4001,  # over max_length=4000
            }
        )

    locs = {tuple(e["loc"]) for e in exc_info.value.errors()}
    assert ("model",) in locs
    assert ("notes",) in locs


def test_valid_input_round_trips() -> None:
    validated = BuyerUpdate.model_validate(
        {"model": "Model 1 (Network)", "profitable_only": True, "ebitda_floor": 5_000_000.0}
    )
    assert validated.model == "Model 1 (Network)"
    assert validated.profitable_only is True
    assert validated.ebitda_floor == 5_000_000.0


def test_everything_optional() -> None:
    validated = BuyerUpdate.model_validate({})
    assert validated.model is None
    assert validated.profitable_only is None
