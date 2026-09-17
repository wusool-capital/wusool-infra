"""Routes a tool name to its own email content builders — the email
counterpart to `pipelines.py`'s `Pipelines.run` dispatch.
"""

from app.modules.lead_magnets.domain.benchmark import email as benchmark_email
from app.modules.lead_magnets.domain.buyer_network import email as buyer_network_email
from app.modules.lead_magnets.domain.readiness import email as readiness_email
from app.modules.lead_magnets.domain.shared.email_content import EmailContent
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs
from app.modules.lead_magnets.domain.valuation import email as valuation_email
from app.modules.utilities.domain.json_types import JsonObject

_BUILDERS = {
    "valuation": valuation_email,
    "readiness": readiness_email,
    "benchmark": benchmark_email,
    "buyer_network": buyer_network_email,
}


def build_confirmation_email(tool: str, payload: JsonObject) -> EmailContent:
    return _BUILDERS[tool].build_confirmation(payload)


def build_internal_email(
    tool: str, payload: JsonObject, ai: JsonObject, subjects: SubjectRefs
) -> EmailContent:
    return _BUILDERS[tool].build_internal(payload, ai, subjects)
