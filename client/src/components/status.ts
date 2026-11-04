export type Status =
  | "running"
  | "completed"
  | "stale"
  | "failed"
  | "pending_review"
  | "approved"
  | "rejected"
  | "coming_soon";

export function candidateStatus(status: string): Status {
  if (status === "APPROVED") return "approved";
  if (status === "REJECTED") return "rejected";
  return "pending_review";
}
