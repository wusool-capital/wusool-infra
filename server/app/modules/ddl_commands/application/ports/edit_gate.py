"""Lets the module that owns a popup react while `/edit-buyer`'s form is saving
on top of it. `ddl_commands` implements nothing here and never imports the
popup's module: `server/main.py` wires an implementation at startup, the same
way `discrepancies` gets its criteria reader.

`gate_state` is opaque to this module; only the implementation decodes it.
"""

from typing import Protocol


class EditGatePort(Protocol):
    async def saving(self, *, gate_view_id: str, gate_state: str) -> None:
        """The form was submitted and the write is about to start."""
        ...

    async def finished(self, *, gate_view_id: str, gate_state: str) -> None:
        """The write ended, whether it saved or failed."""
        ...
