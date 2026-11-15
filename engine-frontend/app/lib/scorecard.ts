import type { ScorecardMetric } from "../demo/types";

export type MetricStatus = "On track" | "At risk" | "Behind";

const WORKDAYS_PER_WEEK = 5;

// Pace rule: compare the actual with the share of the target expected by today.
// Scoring is a rule in code, never AI (CLAUDE.md AI usage policy).
export function metricStatus(actual: number, target: number, workdaysElapsed: number): MetricStatus {
  const expected = (target * workdaysElapsed) / WORKDAYS_PER_WEEK;
  if (actual >= expected) return "On track";
  if (actual >= expected * 0.5) return "At risk";
  return "Behind";
}

/** A yes-no metric is on track once done and at risk until then; counts follow the pace rule. */
export function metricState(metric: ScorecardMetric, workdaysElapsed: number): MetricStatus {
  if (metric.kind === "yes-no") return metric.done ? "On track" : "At risk";
  return metricStatus(metric.taggedIds.length, metric.target, workdaysElapsed);
}
