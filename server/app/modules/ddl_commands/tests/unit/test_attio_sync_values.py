from datetime import date, datetime

from app.modules.attio.providers.attio import values as v


def _item(**kwargs) -> dict:
    return {"active_until": None, **kwargs}


def test_first_prefers_plain_value() -> None:
    values = {"name": [_item(value="Acme")]}
    assert v.first(values, "name") == "Acme"


def test_first_falls_back_to_option_title() -> None:
    values = {"stage": [_item(option={"title": "In Progress"})]}
    assert v.first(values, "stage") == "In Progress"


def test_first_ignores_superseded_entries() -> None:
    values = {"name": [{"active_until": "2024-01-01T00:00:00Z", "value": "Old"}]}
    assert v.first(values, "name") is None


def test_titles_dedupes_preserving_order() -> None:
    values = {
        "sector_focus": [
            _item(option={"title": "Healthcare"}),
            _item(option={"title": "Fintech"}),
            _item(option={"title": "Healthcare"}),
        ]
    }
    assert v.titles(values, "sector_focus") == ["Healthcare", "Fintech"]


def test_ref_returns_target_record_id() -> None:
    values = {"company": [_item(target_record_id="org-123")]}
    assert v.ref(values, "company") == "org-123"


def test_ref_returns_none_when_empty() -> None:
    assert v.ref({}, "company") is None


def test_boolean_parses_checkbox_true() -> None:
    values = {"is_active": [_item(value=True)]}
    assert v.boolean(values, "is_active") is True


def test_boolean_missing_is_none_not_false() -> None:
    """Distinguishing "never set" from "explicitly false" matters to callers
    (see upsert.py's `_reconcile_active_entry`, which treats `None` and
    `False` differently from confirmed `True` when deciding what to patch)."""
    assert v.boolean({}, "is_active") is None


def test_money_reads_currency_value() -> None:
    values = {"check_size_min": [_item(currency_value=500000, currency_code="AED")]}
    assert v.money(values, "check_size_min") == {"amount": 500000, "currency": "AED"}


def test_money_returns_none_for_blank_amount() -> None:
    values = {"check_size_min": [_item(currency_value="", currency_code="AED")]}
    assert v.money(values, "check_size_min") is None


def test_date_parses_into_a_date_object() -> None:
    """`first`'s raw value is a bare `"YYYY-MM-DD"` string — asyncpg rejects
    that for a `DATE` column (needs `datetime.date`), which is exactly what
    broke `sync_seller_role` on a real `last_attempt_date` value.
    """
    values = {"last_attempt_date": [_item(date="2026-08-24")]}
    assert v.date(values, "last_attempt_date") == date(2026, 8, 24)


def test_date_returns_none_when_missing() -> None:
    assert v.date({}, "last_attempt_date") is None


def test_timestamp_parses_into_a_datetime_object() -> None:
    values = {"last_interaction_at": [_item(timestamp="2026-08-24T10:00:00.000000000Z")]}
    assert v.timestamp(values, "last_interaction_at") == datetime.fromisoformat(
        "2026-08-24T10:00:00.000000000Z"
    )


def test_timestamp_returns_none_when_missing() -> None:
    assert v.timestamp({}, "last_interaction_at") is None


def test_parent_id_from_dict_shape() -> None:
    entry = {"parent_record_id": {"record_id": "org-abc"}}
    assert v.parent_id(entry) == "org-abc"


def test_parent_id_from_plain_string_shape() -> None:
    entry = {"parent_record_id": "org-abc"}
    assert v.parent_id(entry) == "org-abc"


def test_entry_id_from_id_object() -> None:
    entry = {"id": {"entry_id": "entry-1"}}
    assert v.entry_id(entry) == "entry-1"
