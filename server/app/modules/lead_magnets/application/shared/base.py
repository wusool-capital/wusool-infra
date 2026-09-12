"""The one shared constructor behind `service.py`'s facade.

Composition, not the multiple-inheritance mixin split `modular-monolith`
generally prescribes: `Pipelines` and `SubmissionService` take genuinely
different Ports (`llm` alone vs. `tool_runs`/`attio`/an AI-runner
callable), so they were never one concern with shared constructor state —
and each is deliberately tested standalone (`test_valuation_ai.py` builds a
bare `Pipelines`; `test_submit.py`/`test_write_contract_e2e.py` inject fake
`run_ai`/`fallback` callables into a bare `SubmissionService`, independent
of `Pipelines` entirely). Forcing them into sibling mixins would make every
one of those tests fake Ports it has no use for. This base only wires
`SubmissionService`'s existing `AiRunner`/`FallbackRunner` Port-shaped
callables to a real `Pipelines`, so `bootstrap.py` has one object to build
instead of two.
"""

from app.modules.lead_magnets.application.shared.pipelines import Pipelines
from app.modules.lead_magnets.application.shared.ports import (
    AttioWriterPort,
    LeadLLMPort,
    ToolRunsPort,
)
from app.modules.lead_magnets.application.shared.submit import SubmissionService


class ServiceBase:
    def __init__(
        self, *, tool_runs: ToolRunsPort, attio: AttioWriterPort, llm: LeadLLMPort
    ) -> None:
        self._pipelines = Pipelines(llm)
        self._submissions = SubmissionService(
            tool_runs=tool_runs,
            attio=attio,
            run_ai=self._pipelines.run,
            fallback=self._pipelines.fallback,
        )
