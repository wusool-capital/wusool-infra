from typing import Annotated

import pytest
from pydantic import Field, TypeAdapter

from app.modules.activities import (
    ActivityPayload,
    CrmRecordPayload,
    LinkedInScanPayload,
    MatchDecisionPayload,
    MatchRunPayload,
    MeetingPayload,
    NoPayload,
    ProfileWritePayload,
    StageChangePayload,
)

_ADAPTER = TypeAdapter(Annotated[ActivityPayload, Field(discriminator="kind")])


@pytest.mark.parametrize(
    "payload",
    [
        NoPayload(),
        CrmRecordPayload(attio_event_type="record.updated", attio_object="deal"),
        ProfileWritePayload(changed_fields=("name", "website"), is_new_org=True),
        MatchRunPayload(candidate_count=5),
        MatchDecisionPayload(deal_attio_id="d-1"),
        MeetingPayload(pushed_to_attio=True),
        StageChangePayload(from_stage="Inbound", to_stage="Qualified"),
        LinkedInScanPayload(new_posts=3, new_job_changes=1, contacts_scanned=2),
    ],
)
def test_payload_round_trips_through_json(payload: ActivityPayload) -> None:
    assert _ADAPTER.validate_json(_ADAPTER.dump_json(payload)) == payload


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError):
        _ADAPTER.validate_json('{"kind": "nope"}')
