import type { OpenToSelling } from "../../demo/types";

// Reuses the counterparty pill tones; the text always carries the meaning.
const TONES: Record<OpenToSelling, string> = {
  Unknown: "pill--not-started",
  Interested: "pill--talks",
  "Warm intro": "pill--closed",
};

export function OpenToSellingPill({ value }: { value: OpenToSelling }) {
  return <span className={`pill ${TONES[value]}`}>{value}</span>;
}
