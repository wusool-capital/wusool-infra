// Follow-up dates are rules in code (PRD R2): 4 and 9 working days after the first
// message, Saturday and Sunday off, and a reply pauses them.
import type { Counterparty } from "../demo/types";

export const FOLLOW_UP_DAYS = [4, 9] as const;

export function addWorkingDays(day: string, workingDays: number) {
  const date = new Date(`${day}T12:00:00Z`);
  let added = 0;
  while (added < workingDays) {
    date.setUTCDate(date.getUTCDate() + 1);
    const weekday = date.getUTCDay();
    if (weekday !== 0 && weekday !== 6) added += 1;
  }
  return date.toISOString().slice(0, 10);
}

export type FollowUp =
  | { state: "due"; date: string }
  | { state: "replied" }
  | { state: "done" }
  | { state: "not-started" };

export function followUp(row: Counterparty): FollowUp {
  const outreach = row.outreach;
  if (!outreach) return { state: "not-started" };
  if (outreach.repliedAt) return { state: "replied" };
  if (outreach.followUpsSent >= FOLLOW_UP_DAYS.length) return { state: "done" };
  return { state: "due", date: addWorkingDays(outreach.firstSentAt, FOLLOW_UP_DAYS[outreach.followUpsSent]) };
}
