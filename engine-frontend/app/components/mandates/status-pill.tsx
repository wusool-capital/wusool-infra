import type { CounterpartyStatus } from "../../demo/types";

// Pipeline status pills from DESIGN.md: each status keeps its text, colour only supports it.
const TONES: Record<CounterpartyStatus, string> = {
  "Not contacted": "pill--not-started",
  Contacted: "pill--contacted",
  "Initial conversations": "pill--talks",
  LOI: "pill--loi",
  "Due diligence": "pill--diligence",
  "Bidding offer": "pill--bidding",
  Closed: "pill--closed",
  Passed: "pill--passed",
};

export function StatusPill({ status }: { status: CounterpartyStatus }) {
  return <span className={`pill ${TONES[status]}`}>{status}</span>;
}
