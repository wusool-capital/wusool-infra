// Reuses the counterparty pill tones; the text always carries the meaning.
const TONES: Record<string, string> = {
  Active: "pill--closed",
  Dormant: "pill--not-started",
  "Do not contact": "pill--passed",
};

/** Demo statuses are Active, Dormant and Do not contact; live shows Attio's mandate status. */
export function BuyerStatusPill({ status }: { status: string | null }) {
  if (status === null) return <span className="muted">Not set</span>;
  return <span className={`pill ${TONES[status] ?? "pill--not-started"}`}>{status}</span>;
}
