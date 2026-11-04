import { Badge } from "@/components/ui/badge";

import type { Status } from "./status";

const STATUS: Record<
  Status,
  {
    label: string;
    tone: "neutral" | "running" | "success" | "warning" | "danger" | "plain";
  }
> = {
  running: { label: "Running", tone: "running" },
  completed: { label: "Completed", tone: "success" },
  stale: { label: "Stale", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
  pending_review: { label: "Pending review", tone: "neutral" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  coming_soon: { label: "Coming soon", tone: "plain" },
};

export function StatusBadge({ status }: { status: Status }): React.JSX.Element {
  const { label, tone } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
