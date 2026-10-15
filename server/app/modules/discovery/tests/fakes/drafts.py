"""Builds the draft tokens old Slack buttons still carry, for tests of `decode_draft`."""

import json
from dataclasses import asdict

from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.utilities import get_shared_ephemeral_store


def store_draft(draft: SellerDraft) -> str:
    return get_shared_ephemeral_store().put(json.dumps(asdict(draft), default=str))
