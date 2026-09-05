"use client";

// Matches the fields app.ai.summarizer.HierarchicalSummarizer produces
// (see app/ai/domain.py) -- rendered in this order, empty ones skipped.
const SUMMARY_LIST_SECTIONS: { key: string; heading: string }[] = [
  { key: 'discussion_topics', heading: 'Discussion Topics' },
  { key: 'action_items', heading: 'Action Items' },
  { key: 'decisions', heading: 'Decisions' },
  { key: 'open_questions', heading: 'Open Questions' },
  { key: 'risks', heading: 'Risks' },
  { key: 'keywords', heading: 'Keywords' },
];

// Plain-text rendering of the same fields SummaryView displays, in the same
// order -- used to build the string for the copy-to-clipboard action.
export function summaryToPlainText(summary: Record<string, unknown>): string {
  const executiveSummary = typeof summary.executive_summary === 'string' ? summary.executive_summary : '';
  const parts: string[] = [];
  if (executiveSummary.trim()) parts.push(executiveSummary.trim());

  for (const { key, heading } of SUMMARY_LIST_SECTIONS) {
    const items = summary[key];
    if (!Array.isArray(items) || items.length === 0) continue;
    parts.push(`${heading}\n${items.map((item) => `- ${String(item)}`).join('\n')}`);
  }

  return parts.join('\n\n');
}

export function SummaryView({ summary }: { summary: Record<string, unknown> }) {
  const executiveSummary = typeof summary.executive_summary === 'string' ? summary.executive_summary : '';
  // Preserve paragraph breaks the same way Slack's mrkdwn does -- HTML
  // collapses whitespace by default, so a single <p> flattens a
  // multi-paragraph summary into one dense block.
  const paragraphs = executiveSummary.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  return (
    <div className="space-y-4 text-sm text-foreground ">
      {paragraphs.length > 0 && (
        <div className="space-y-3">
          {paragraphs.map((paragraph, i) => (
            <p key={i} className="leading-relaxed whitespace-pre-wrap">{paragraph}</p>
          ))}
        </div>
      )}
      {SUMMARY_LIST_SECTIONS.map(({ key, heading }) => {
        const items = summary[key];
        if (!Array.isArray(items) || items.length === 0) return null;
        return (
          <div key={key}>
            <h4 className="font-semibold text-foreground mb-1">{heading}</h4>
            <ul className="list-disc pl-5 space-y-0.5">
              {items.map((item, i) => (
                <li key={i}>{String(item)}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
