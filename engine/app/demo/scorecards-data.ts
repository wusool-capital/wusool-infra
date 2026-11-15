// Invented scorecards for Hugo and Ramzy, and eight past weeks for every advisor (PRD K1, K2).
import type { Scorecard, ScorecardWeek } from "./types";

// Each person keeps their own list; Ramzy does not track partner catch-ups.
export const moreScorecards: Scorecard[] = [
  {
    ownerId: "hugo",
    weekOf: "2026-11-09",
    workdaysElapsed: 2,
    metrics: [
      { id: "s-new-buyer", label: "New buyer conversations", kind: "count", target: 4, taggedIds: ["p-noura", "p-james"] },
      { id: "s-buyer-catchup", label: "Buyer catch-ups", kind: "count", target: 5, taggedIds: ["p-ziad"] },
      { id: "s-partner-catchup", label: "Referral partner catch-ups", kind: "count", target: 3, taggedIds: ["p-tom", "p-hessa"] },
      { id: "s-linkedin", label: "LinkedIn schedule followed", kind: "yes-no", target: 1, taggedIds: [], done: false },
    ],
    suggestedPersonIds: ["p-hessa"],
  },
  {
    ownerId: "ramzy",
    weekOf: "2026-11-09",
    workdaysElapsed: 2,
    metrics: [
      { id: "s-new-buyer", label: "New buyer conversations", kind: "count", target: 6, taggedIds: ["p-faisal", "p-rami"] },
      { id: "s-buyer-catchup", label: "Buyer catch-ups", kind: "count", target: 3, taggedIds: [] },
      { id: "s-linkedin", label: "LinkedIn schedule followed", kind: "yes-no", target: 1, taggedIds: [], done: true },
    ],
    suggestedPersonIds: ["p-rami", "p-priya"],
  },
];

const WEEKS = ["2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02"];

// Actuals per finished week, oldest first, for each owner and metric. Yes or no is 1 or 0.
const ACTUALS: Record<string, Record<string, number[]>> = {
  jules: { "s-new-buyer": [4, 6, 5, 3, 5, 7, 4, 6], "s-buyer-catchup": [3, 4, 4, 5, 2, 4, 6, 4], "s-partner-catchup": [1, 2, 3, 2, 1, 2, 2, 3], "s-linkedin": [1, 1, 0, 1, 1, 0, 1, 1] },
  hugo: { "s-new-buyer": [5, 4, 6, 5, 3, 5, 6, 4], "s-buyer-catchup": [2, 3, 4, 3, 5, 4, 2, 3], "s-partner-catchup": [3, 2, 4, 3, 1, 3, 3, 2], "s-linkedin": [0, 1, 1, 1, 0, 1, 1, 0] },
  ramzy: { "s-new-buyer": [3, 2, 4, 5, 4, 3, 4, 2], "s-buyer-catchup": [3, 2, 3, 4, 3, 3, 2, 4], "s-linkedin": [1, 1, 1, 0, 1, 1, 1, 1] },
};

export const scorecardHistory: ScorecardWeek[] = Object.entries(ACTUALS).flatMap(([ownerId, metrics]) =>
  WEEKS.map((weekOf, index) => ({ ownerId: ownerId as ScorecardWeek["ownerId"], weekOf, actuals: Object.fromEntries(Object.entries(metrics).map(([id, values]) => [id, values[index]])) })),
);
