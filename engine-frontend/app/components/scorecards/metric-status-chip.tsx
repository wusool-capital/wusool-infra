import type { MetricStatus } from "../../lib/scorecard";

// RAG: green, amber, red from the shared pill tones. The word always says it too.
const TONES: Record<MetricStatus, string> = {
  "On track": "pill pill--closed",
  "At risk": "pill pill--talks",
  Behind: "pill pill--passed",
};

export function MetricStatusChip({ status }: { status: MetricStatus }) {
  return <span className={TONES[status]}>{status}</span>;
}
