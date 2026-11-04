import { useRef } from "react";

import { candidateStatus } from "@/components/status";
import { StatusBadge } from "@/components/StatusBadge";
import type { CandidateRead } from "@/gen/types/CandidateRead";
import { score } from "@/lib/format";
import { cn } from "@/lib/utils";

import { ScoreFigure } from "./ScoreBar";

export interface CandidateGroup {
  id: string;
  title: string;
  candidates: CandidateRead[];
}

const DECISION_TEXT: Record<string, string> = {
  APPROVED: "Approved",
  REJECTED: "Rejected",
};

function Row({
  candidate,
  threshold,
  selected,
  onSelect,
}: {
  candidate: CandidateRead;
  threshold: number;
  selected: boolean;
  onSelect: () => void;
}): React.JSX.Element {
  const discovered = candidate.origin === "discovery";
  return (
    <button
      type="button"
      data-candidate={candidate.id}
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        "relative grid min-h-14 w-full cursor-pointer grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-sm px-md py-[10px] text-left transition-colors focus-visible:-outline-offset-1 sm:grid-cols-[24px_minmax(0,1fr)_auto_auto]",
        selected
          ? "bg-surface-3 before:absolute before:inset-y-0 before:left-0 before:w-px before:bg-primary before:content-['']"
          : "hover:bg-surface-2",
      )}
    >
      <span className="text-body text-ink-subtle">
        {discovered ? null : candidate.rank}
      </span>
      <span className="flex min-w-0 flex-col gap-[2px]">
        <span className="truncate text-body font-medium text-ink">
          {candidate.seller_org_name}
        </span>
        <span className="truncate text-small text-ink-subtle">
          {discovered
            ? researchNote(candidate)
            : `Confidence ${score(candidate.data_confidence)}`}
          <span className="sm:hidden">
            {" "}
            · {DECISION_TEXT[candidate.status] ?? "To review"}
          </span>
        </span>
      </span>
      <span className="hidden w-[92px] justify-self-end text-right sm:block">
        {candidate.status === "PENDING_REVIEW" ? (
          <span className="text-small text-ink-subtle">To review</span>
        ) : (
          <StatusBadge status={candidateStatus(candidate.status)} />
        )}
      </span>
      <ScoreFigure value={candidate.match_score} threshold={threshold} />
    </button>
  );
}

function researchNote(candidate: CandidateRead): string {
  const research = candidate.research;
  if (research?.status === "running") return "Researching…";
  if (research?.status === "done" && !research.reviewed)
    return "Research to review";
  return "Google Maps lead · not scored";
}

// The ranked shortlist; ↑/↓ move the selection, and a phone opens the detail in place.
export function CandidateList({
  groups,
  threshold,
  selectedId,
  onSelect,
  inlineDetail,
}: {
  groups: CandidateGroup[];
  threshold: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
  inlineDetail?: React.ReactNode;
}): React.JSX.Element {
  const root = useRef<HTMLDivElement>(null);
  const order = groups.flatMap((g) => g.candidates.map((c) => c.id));

  const onKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const index = selectedId === null ? -1 : order.indexOf(selectedId);
    const step = event.key === "ArrowDown" ? 1 : -1;
    const next = order[Math.max(0, Math.min(order.length - 1, index + step))];
    if (next === undefined) return;
    event.preventDefault();
    onSelect(next);
    root.current
      ?.querySelector<HTMLButtonElement>(`[data-candidate="${next}"]`)
      ?.focus();
  };

  return (
    <div
      ref={root}
      onKeyDown={onKeyDown}
      className="flex flex-col overflow-hidden rounded-lg border border-hairline bg-surface-1"
    >
      {groups.map((group) => (
        <section key={group.id} aria-labelledby={`group-${group.id}`}>
          <div className="flex items-center justify-between border-b border-hairline px-md py-xs text-small text-ink-subtle [section+section_&]:border-t">
            <h3 id={`group-${group.id}`}>{group.title}</h3>
            <span aria-hidden className="flex items-center gap-sm">
              <span className="hidden w-[92px] text-right sm:block">
                Decision
              </span>
              <span className="w-14 text-right">Score</span>
            </span>
          </div>
          <ul>
            {group.candidates.map((candidate) => (
              <li
                key={candidate.id}
                className="border-b border-hairline last:border-b-0"
              >
                <Row
                  candidate={candidate}
                  threshold={threshold}
                  selected={candidate.id === selectedId}
                  onSelect={() => {
                    onSelect(candidate.id);
                  }}
                />
                {candidate.id === selectedId && inlineDetail && (
                  <div className="border-t border-hairline bg-surface-2 px-md py-lg">
                    {inlineDetail}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
