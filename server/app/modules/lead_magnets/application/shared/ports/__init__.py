"""Every seam `application/` depends on: the LLM, the web search, the Attio
write, the ledger, the report CMS and renderer, and the Webflow Reports
collection — one Protocol per file, re-exported here as this package's
public surface so existing `from .ports import X` call sites are unaffected
by the split.
"""

from app.modules.lead_magnets.application.shared.ports.attio import AttioWriterPort
from app.modules.lead_magnets.application.shared.ports.llm import LeadLLMPort
from app.modules.lead_magnets.application.shared.ports.report_renderer import ReportRendererPort
from app.modules.lead_magnets.application.shared.ports.report_source import ReportSourcePort
from app.modules.lead_magnets.application.shared.ports.reports_cms import ReportsCmsPort
from app.modules.lead_magnets.application.shared.ports.search import SearchPort
from app.modules.lead_magnets.application.shared.ports.tool_runs import ToolRunsPort

__all__ = [
    "AttioWriterPort",
    "LeadLLMPort",
    "ReportRendererPort",
    "ReportSourcePort",
    "ReportsCmsPort",
    "SearchPort",
    "ToolRunsPort",
]
