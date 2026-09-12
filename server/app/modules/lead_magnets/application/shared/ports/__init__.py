"""Every seam `application/` depends on: the LLM, the web search, the Attio
write, and the ledger — one Protocol per file, re-exported here as this
package's public surface so existing `from .ports import X` call sites are
unaffected by the split.
"""

from app.modules.lead_magnets.application.shared.ports.attio import AttioWriterPort
from app.modules.lead_magnets.application.shared.ports.llm import LeadLLMPort
from app.modules.lead_magnets.application.shared.ports.search import SearchPort
from app.modules.lead_magnets.application.shared.ports.tool_runs import ToolRunsPort

__all__ = [
    "AttioWriterPort",
    "LeadLLMPort",
    "SearchPort",
    "ToolRunsPort",
]
