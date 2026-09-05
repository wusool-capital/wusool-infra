"""Composition root for this module: will hold the `build_*` factory
functions `api/dependencies.py` consumes instead of constructing concrete
persistence/provider classes inline. NOT the deployed entrypoint —
`server/main.py` owns that, same as the other modules.

Empty for now; phase-core wires the real Bedrock/persistence/Attio
factories in here.
"""


# TODO(phase-core): replace with the real service factory once
# domain/application/persistence/providers land.
def build_meetings_service() -> None: ...
