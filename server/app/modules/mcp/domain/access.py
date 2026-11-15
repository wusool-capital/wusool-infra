"""Who is calling, and what a tool needs from them."""

from dataclasses import dataclass
from typing import Literal

Permission = Literal[
    "buyers.read",
    "buyers.write",
    "sellers.read",
    "sellers.write",
    "imports.write",
]

# The one token scope v1 issues. A later area adds its own scope rather than widening this.
CRM_SCOPE = "crm"


@dataclass(frozen=True)
class Caller:
    slack_user_id: str
    team_id: str
    name: str | None
    scopes: tuple[str, ...]
