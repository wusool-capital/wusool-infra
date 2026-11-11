"use client";

import type { ReactNode } from 'react';
import { hasDealSignal, parsePushedSummary, splitLead, splitOwner } from '@/lib/pushedSummary';

/** Bolds a short "On observability:" style lead-in, which older summaries used as a sub-heading. */
function withLeadIn(paragraph: string): ReactNode {
  const match = /^(On [^:]{1,40}:)\s+([\s\S]*)$/.exec(paragraph);
  if (!match) return paragraph;
  return (
    <>
      <strong className="font-semibold">{match[1]}</strong> {match[2]}
    </>
  );
}

function Gist({ paragraphs }: { paragraphs: string[] }) {
  // A new gist is one paragraph whose first sentence is the outcome; older summaries open with several.
  if (paragraphs.length === 1) {
    const { lead, rest } = splitLead(paragraphs[0]);
    return (
      <p className="whitespace-pre-wrap">
        <strong className="font-semibold">{lead}</strong>
        {rest && ` ${rest}`}
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {paragraphs.map((paragraph, i) => (
        // pre-wrap keeps the summarizer's single line breaks, which HTML would collapse.
        <p key={i} className="whitespace-pre-wrap">
          {withLeadIn(paragraph)}
        </p>
      ))}
    </div>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return <h2 className="mb-2 text-base font-semibold text-foreground">{children}</h2>;
}

function Bullets({ items, owners = false }: { items: string[]; owners?: boolean }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((item, i) => {
        const { owner, action } = owners ? splitOwner(item) : { owner: null, action: item };
        return (
          <li key={i}>
            {owner ? (
              <>
                <strong className="font-semibold">{owner}:</strong> {action}
              </>
            ) : (
              action
            )}
          </li>
        );
      })}
    </ul>
  );
}

function ListSection({ heading, items, owners }: { heading: string; items: string[]; owners?: boolean }) {
  if (items.length === 0) return null;
  return (
    <section>
      <Heading>{heading}</Heading>
      <Bullets items={items} owners={owners} />
    </section>
  );
}

function SubSection({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold text-foreground">{heading}</h3>
      {children}
    </div>
  );
}

export function SummaryView({ summary: raw }: { summary: Record<string, unknown> }) {
  const summary = parsePushedSummary(raw);
  const dealSignal = hasDealSignal(summary);
  return (
    // ~70 characters per line keeps long summaries comfortable to read.
    <div className="max-w-[70ch] select-text space-y-8 text-base leading-relaxed text-foreground">
      {summary.gist.length > 0 && <Gist paragraphs={summary.gist} />}
      <ListSection heading="Next steps" items={summary.nextSteps} owners />
      <ListSection heading="Decisions" items={summary.decisions} />
      {dealSignal ? (
        <section>
          <Heading>Deal signal</Heading>
          <div className="space-y-4">
            {summary.momentum && (
              <SubSection heading="Momentum">
                <p>{summary.momentum}</p>
              </SubSection>
            )}
            {summary.toVerify.length > 0 && (
              <SubSection heading="To verify">
                <Bullets items={summary.toVerify} />
              </SubSection>
            )}
            {summary.risks.length > 0 && (
              <SubSection heading="Risks">
                <Bullets items={summary.risks} />
              </SubSection>
            )}
          </div>
        </section>
      ) : (
        <ListSection heading="Risks" items={summary.risks} />
      )}
      {summary.notes.length > 0 && (
        <section>
          <Heading>Notes</Heading>
          <div className="space-y-4">
            {summary.notes.map((note, i) => (
              <SubSection key={i} heading={note.topic}>
                <Bullets items={note.points} />
              </SubSection>
            ))}
          </div>
        </section>
      )}
      {summary.legacy.map((section) => (
        <ListSection key={section.heading} heading={section.heading} items={section.items} />
      ))}
    </div>
  );
}
