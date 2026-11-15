import type { BuyerStatus } from "../../demo/types";

// Reuses the counterparty pill tones; the text always carries the meaning.
const TONES: Record<BuyerStatus, string> = {
  Active: "pill--closed",
  Dormant: "pill--not-started",
  "Do not contact": "pill--passed",
};

export function BuyerStatusPill({ status }: { status: BuyerStatus }) {
  return <span className={`pill ${TONES[status]}`}>{status}</span>;
}
