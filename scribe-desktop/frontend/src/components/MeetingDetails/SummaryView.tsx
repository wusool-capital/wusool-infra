"use client";

import type { ReactNode } from 'react';

// Fields app.ai.summarizer.HierarchicalSummarizer produces (see app/ai/domain.py); empty ones are skipped.
type Section = { key: string; heading: string };

// What people open a summary for comes first; context and loose ends follow the narrative.
const LEAD_SECTIONS: Section[] = [
  { key: 'action_items', heading: 'Action Items' },
  { key: 'decisions', heading: 'Decisions' },
];
const TRAILING_SECTIONS: Section[] = [
  { key: 'discussion_topics', heading: 'Discussion Topics' },
  { key: 'open_questions', heading: 'Open Questions' },
  { key: 'risks', heading: 'Risks' },
];

function items(summary: Record<string, unknown>, key: string): string[] {
  const value = summary[key];
  return Array.isArray(value) ? value.map(String).filter((item) => item.trim() !== '') : [];
}

function paragraphs(summary: Record<string, unknown>): string[] {
  const text = typeof summary.executive_summary === 'string' ? summary.executive_summary : '';
  return text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
}

/** Plain text in the same order SummaryView shows, for the copy action. */
export function summaryToPlainText(summary: Record<string, unknown>): string {
  const parts: string[] = [];
  const list = ({ key, heading }: Section) => {
    const entries = items(summary, key);
    if (entries.length > 0) parts.push(`${heading}\n${entries.map((item) => `- ${item}`).join('\n')}`);
  };
  LEAD_SECTIONS.forEach(list);
  const prose = paragraphs(summary);
  if (prose.length > 0) parts.push(`Summary\n${prose.join('\n\n')}`);
  TRAILING_SECTIONS.forEach(list);
  const keywords = items(summary, 'keywords');
  if (keywords.length > 0) parts.push(`Keywords: ${keywords.join(', ')}`);
  return parts.join('\n\n');
}

/** Bolds a short "On observability:" style lead-in, which the summarizer uses as a sub-heading. */
function withLeadIn(paragraph: string): ReactNode {
  const match = /^(On [^:]{1,40}:)\s+([\s\S]*)$/.exec(paragraph);
  if (!match) return paragraph;
  return (
    <>
      <strong className="font-semibold">{match[1]}</strong> {match[2]}
    </>
  );
}

function ListSection({ summary, section }: { summary: Record<string, unknown>; section: Section }) {
  const entries = items(summary, section.key);
  if (entries.length === 0) return null;
  return (
    <section>
      <h2 className="mb-2 text-base font-semibold text-foreground">{section.heading}</h2>
      <ul className="list-disc space-y-1 pl-5">
        {entries.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export function SummaryView({ summary }: { summary: Record<string, unknown> }) {
  const prose = paragraphs(summary);
  const keywords = items(summary, 'keywords');
  return (
    // ~70 characters per line keeps long summaries comfortable to read.
    <div className="max-w-[70ch] select-text space-y-8 text-base leading-relaxed text-foreground">
      {LEAD_SECTIONS.map((section) => (
        <ListSection key={section.key} summary={summary} section={section} />
      ))}
      {prose.length > 0 && (
        <section>
          <h2 className="mb-2 text-base font-semibold text-foreground">Summary</h2>
          <div className="space-y-3">
            {prose.map((paragraph, i) => (
              // pre-wrap keeps the summarizer's single line breaks, which HTML would collapse.
              <p key={i} className="whitespace-pre-wrap">
                {withLeadIn(paragraph)}
              </p>
            ))}
          </div>
        </section>
      )}
      {TRAILING_SECTIONS.map((section) => (
        <ListSection key={section.key} summary={summary} section={section} />
      ))}
      {keywords.length > 0 && (
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Keywords:</span> {keywords.join(' · ')}
        </p>
      )}
    </div>
  );
}
