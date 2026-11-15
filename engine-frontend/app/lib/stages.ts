// Simplified deal stages agreed on 6 Nov 2026 (PRD decisions table). Engaged added 7 Nov 2026:
// the client said yes and the proposal, NDA and contract are being signed. Marketing renamed
// Outreach (9 Nov 2026): the step covers sell-side marketing and buy-side target approaches.
// Offers renamed Non-binding offers (9 Nov 2026): IOIs and LOIs received before one is signed with exclusivity.
export const STAGES = [
  "Lead",
  "Qualified",
  "Engaged",
  "Mandate signed",
  "Preparation",
  "Outreach",
  "Non-binding offers",
  "Due diligence",
  "Closing",
  "Closed",
] as const;

export type Stage = (typeof STAGES)[number];

export function stagePosition(stage: Stage) {
  return `${STAGES.indexOf(stage) + 1} of ${STAGES.length}`;
}

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * Days spent in each stage up to the current one: from the date a stage was entered to the date
 * the next recorded stage was entered, or to today for the current stage. Stages without a date are left out.
 */
export function daysPerStage(enteredAt: Partial<Record<Stage, string>>, current: Stage, now: string) {
  const reached = STAGES.slice(0, STAGES.indexOf(current) + 1).filter((stage) => enteredAt[stage]);
  const days: Partial<Record<Stage, number>> = {};
  reached.forEach((stage, index) => {
    const end = index + 1 < reached.length ? enteredAt[reached[index + 1]]! : now.slice(0, 10);
    days[stage] = Math.max(0, Math.round((Date.parse(end) - Date.parse(enteredAt[stage]!)) / DAY_MS));
  });
  return days;
}
