"""Which popup an `/edit-buyer` form was opened from (`/find-match`'s "Before we
match"), so saving can pause and then refresh it. Held server-side: the popup's
own `private_metadata` can run to ~1,000 characters, too much to copy into
every form's metadata.
"""

from pydantic import BaseModel

from app.modules.utilities import get_shared_ephemeral_store


class GateRef(BaseModel):
    view_id: str
    # The popup's `private_metadata`, handed back untouched.
    state: str


def encode_gate_ref(ref: GateRef) -> str:
    return get_shared_ephemeral_store().put(ref.model_dump_json())


def decode_gate_ref(token: str | None) -> GateRef | None:
    """`None` for no token or an expired one; the save still works, the popup
    just isn't refreshed."""
    if token is None:
        return None
    payload = get_shared_ephemeral_store().get(token)
    return None if payload is None else GateRef.model_validate_json(payload)
