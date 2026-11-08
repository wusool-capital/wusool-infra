// Reads the server's meeting summary (server/app/modules/meetings/domain/summary.py).
// Summaries are never regenerated, so older ones still carry discussion_topics/open_questions.

export interface SummaryNote {
  topic: string;
  points: string[];
}

export interface ListSection {
  heading: string;
  items: string[];
}

export interface PushedSummary {
  /** Gist paragraphs; an older summary's long opening lands here too. */
  gist: string[];
  nextSteps: string[];
  decisions: string[];
  momentum: string;
  toVerify: string[];
  risks: string[];
  notes: SummaryNote[];
  legacy: ListSection[];
}

const LEGACY_SECTIONS: [key: string, heading: string][] = [
  ['discussion_topics', 'Discussion Topics'],
  ['open_questions', 'Open Questions'],
];

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.trim() !== '')
    : [];
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function notes(value: unknown): SummaryNote[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item !== 'object' || item === null) return [];
    const note = item as Record<string, unknown>;
    const points = strings(note.points);
    return points.length > 0 ? [{ topic: text(note.topic), points }] : [];
  });
}

export function parsePushedSummary(summary: Record<string, unknown>): PushedSummary {
  return {
    gist: text(summary.executive_summary).split(/\n{2,}/).map((p) => p.trim()).filter(Boolean),
    nextSteps: strings(summary.action_items),
    decisions: strings(summary.decisions),
    momentum: text(summary.deal_momentum),
    toVerify: strings(summary.claims_to_verify),
    risks: strings(summary.risks),
    notes: notes(summary.notes),
    legacy: LEGACY_SECTIONS.map(([key, heading]) => ({ heading, items: strings(summary[key]) })).filter(
      (section) => section.items.length > 0,
    ),
  };
}

/** Deal meetings group momentum, claims to verify and risks; others show plain Risks. */
export function hasDealSignal(summary: PushedSummary): boolean {
  return summary.momentum !== '' || summary.toVerify.length > 0;
}

/** Splits "Sinan: send the request" so the owner can be shown in bold. */
export function splitOwner(item: string): { owner: string | null; action: string } {
  const match = /^([^:\n]{1,40}):\s+([\s\S]+)$/.exec(item);
  return match ? { owner: match[1], action: match[2] } : { owner: null, action: item };
}

// Abbreviations whose full stop doesn't end a sentence.
const ABBREVIATION = /(?:^|\s)(?:[A-Z]\.){1,3}$|\b(?:Mr|Mrs|Ms|Dr|Prof|St|Co|Inc|Ltd|LLC|Corp|vs|etc|e\.g|i\.e|approx|No)\.$/i;

/** Splits off the gist's first sentence, which states where the meeting landed. */
export function splitLead(paragraph: string): { lead: string; rest: string } {
  const boundary = /[.!?](?=\s+\S)/g;
  for (let match = boundary.exec(paragraph); match; match = boundary.exec(paragraph)) {
    const lead = paragraph.slice(0, match.index + 1);
    if (!ABBREVIATION.test(lead)) return { lead, rest: paragraph.slice(match.index + 1).trim() };
  }
  return { lead: paragraph, rest: '' };
}

function bullets(heading: string, items: string[]): string {
  return `${heading}\n${items.map((item) => `- ${item}`).join('\n')}`;
}

/** Plain text in the same order SummaryView shows, for the copy action. */
export function summaryToPlainText(raw: Record<string, unknown>): string {
  const summary = parsePushedSummary(raw);
  const parts: string[] = [];
  if (summary.gist.length > 0) parts.push(summary.gist.join('\n\n'));
  if (summary.nextSteps.length > 0) parts.push(bullets('Next steps', summary.nextSteps));
  if (summary.decisions.length > 0) parts.push(bullets('Decisions', summary.decisions));
  if (hasDealSignal(summary)) {
    const signal = ['Deal signal'];
    if (summary.momentum) signal.push(`Momentum: ${summary.momentum}`);
    if (summary.toVerify.length > 0) signal.push(bullets('To verify', summary.toVerify));
    if (summary.risks.length > 0) signal.push(bullets('Risks', summary.risks));
    parts.push(signal.join('\n'));
  } else if (summary.risks.length > 0) {
    parts.push(bullets('Risks', summary.risks));
  }
  if (summary.notes.length > 0) {
    parts.push(['Notes', ...summary.notes.map((note) => bullets(note.topic, note.points))].join('\n\n'));
  }
  summary.legacy.forEach((section) => parts.push(bullets(section.heading, section.items)));
  return parts.join('\n\n');
}
