"""The optional "Anything specific about this search?" box steers a buyer
search, so it belongs to `/check-buyer` and `/find-match` only. A new flow
(`/enrich-buyer` briefly had one) must not pick it up without a decision.
"""

from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"
_LABEL = "Anything specific about this search?"
_ALLOWED = {
    "modules/discrepancies/api/slack/views/buyer_picker.py",
    "modules/matching_engine/api/slack/views/buyer_selection.py",
}


def test_only_check_buyer_and_find_match_ask_for_context() -> None:
    found = {
        str(path.relative_to(_APP))
        for path in _APP.rglob("*.py")
        if "/tests/" not in str(path) and _LABEL in path.read_text()
    }
    assert found == _ALLOWED
