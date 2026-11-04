import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";

export type StepId =
  "buyer" | "check" | "match" | "shortlist" | "discovery" | "export";
export type StepState =
  "done" | "active" | "upcoming" | "skipped" | "attention";

export const STEP_LABELS: Record<StepId, string> = {
  buyer: "Buyer",
  check: "Profile check",
  match: "Matching",
  shortlist: "Shortlist",
  discovery: "Discovery",
  export: "Export",
};

export const STEP_ORDER: StepId[] = [
  "buyer",
  "check",
  "match",
  "shortlist",
  "discovery",
  "export",
];

export type StepStates = Record<StepId, StepState>;

export function preRunSteps(current: "buyer" | "check"): StepStates {
  return {
    buyer: current === "buyer" ? "active" : "done",
    check: current === "check" ? "active" : "upcoming",
    match: "upcoming",
    shortlist: "upcoming",
    discovery: "upcoming",
    export: "upcoming",
  };
}

export function hasPendingReview(
  run: RunDetailResponse,
  origin: "crm" | "discovery",
): boolean {
  return run.candidates.some(
    (c) => c.origin === origin && c.status === "PENDING_REVIEW",
  );
}

// The run page's position in the flow, derived only from the run's persisted state.
export function runSteps(run: RunDetailResponse): StepStates {
  const base: StepStates = {
    buyer: "done",
    check: "done",
    match: "upcoming",
    shortlist: "upcoming",
    discovery: "upcoming",
    export: "upcoming",
  };
  if (run.state === "running") return { ...base, match: "active" };
  if (run.state === "stale" || run.state === "failed")
    return { ...base, match: "attention" };

  const discoveryStatus = run.discovery.status;
  const discoveryBusy = discoveryStatus === "running";
  const discovery: StepState =
    discoveryStatus === "not_needed"
      ? "skipped"
      : discoveryBusy || discoveryStatus === "available"
        ? "active"
        : hasPendingReview(run, "discovery")
          ? "active"
          : discoveryStatus === "done"
            ? "done"
            : "attention";
  const shortlist: StepState = hasPendingReview(run, "crm") ? "active" : "done";
  const anyPending = shortlist === "active" || discovery === "active";
  return {
    ...base,
    match: "done",
    shortlist,
    discovery,
    export: anyPending ? "upcoming" : "active",
  };
}
