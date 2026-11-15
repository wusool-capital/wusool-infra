// Where each counterparty stands in its outreach, by rule (PRD R1, R2): the Outreach tiles and
// the grouped list both read from here, so a count and its section always agree.
import type { Counterparty } from "../demo/types";
import { FOLLOW_UP_DAYS, followUp } from "./follow-ups";

export const OUTREACH_GROUPS = ["due", "waiting", "replied", "no-contact", "no-reply"] as const;
export type OutreachGroup = (typeof OUTREACH_GROUPS)[number];

export const GROUP_TITLES: Record<OutreachGroup, string> = {
  due: "Due today",
  waiting: "Waiting for a reply",
  replied: "Replied",
  "no-contact": "No contact",
  "no-reply": "No reply after both follow-ups",
};

export type OutreachState = {
  group: OutreachGroup;
  /** Sorts rows inside their group. */
  order: string;
  /** "First message" or "Follow-up 1 of 2". */
  step?: string;
  /** The date that matters for the group: when it is due, or when they replied. */
  date?: string;
  overdue?: boolean;
};

/** `today` is a day key ("2026-11-11") in Dubai time. */
export function outreachState(row: Counterparty, today: string): OutreachState {
  if (row.contactIds.length === 0) return { group: "no-contact", order: row.name };
  const step = followUp(row);
  if (step.state === "not-started") return { group: "due", order: `1-${row.name}`, step: "First message" };
  if (step.state === "replied") return { group: "replied", order: invert(row.outreach!.repliedAt!), date: row.outreach!.repliedAt };
  if (step.state === "done") return { group: "no-reply", order: row.name };
  const label = `Follow-up ${row.outreach!.followUpsSent + 1} of ${FOLLOW_UP_DAYS.length}`;
  if (step.date <= today) return { group: "due", order: `0-${step.date}`, step: label, date: step.date, overdue: step.date < today };
  return { group: "waiting", order: step.date, step: label, date: step.date };
}

// Newest first inside Replied.
function invert(day: string) {
  return String(99999999 - Number(day.replaceAll("-", "")));
}
