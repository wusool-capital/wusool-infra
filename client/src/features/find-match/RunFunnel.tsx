import type { CandidateRead } from "@/gen/types/CandidateRead";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";
import { score } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Cell {
  label: string;
  value: string;
  note: string;
}

function cells(run: RunDetailResponse): Cell[] {
  const crm = run.candidates.filter((c) => c.origin === "crm");
  const found = run.candidates.length - crm.length;
  const approved = run.candidates.filter((c) => c.status === "APPROVED").length;
  const pending = run.candidates.filter(
    (c) => c.status === "PENDING_REVIEW",
  ).length;
  const done = run.state === "completed";
  return [
    {
      label: "Sellers considered",
      value: score(run.candidates_considered),
      note: "Eligible in the CRM",
    },
    {
      label: "Passed filters",
      value: score(run.candidates_filtered),
      note: "Sector, geography, size",
    },
    {
      label: "Shortlisted",
      value: done ? String(crm.length) : "—",
      note:
        found > 0 ? `+${String(found)} found outside` : "Ranked with reasons",
    },
    {
      label: "Approved",
      value: done ? String(approved) : "—",
      note: !done
        ? "After review"
        : pending > 0
          ? `${String(pending)} left to review`
          : "Every candidate decided",
    },
  ];
}

// The run narrowing the CRM down to a shortlist, one divided strip.
export function RunFunnel({
  run,
}: {
  run: RunDetailResponse;
}): React.JSX.Element {
  return (
    <dl className="grid grid-cols-2 rounded-lg border border-hairline bg-surface-1 sm:grid-cols-4">
      {cells(run).map((cell, index) => (
        <div
          key={cell.label}
          className={cn(
            "flex flex-col gap-xxs px-md py-sm",
            index > 0 && "sm:border-l sm:border-hairline",
            index % 2 === 1 && "border-l border-hairline",
            index > 1 && "border-t border-hairline sm:border-t-0",
          )}
        >
          <dt className="text-small text-ink-subtle">{cell.label}</dt>
          <dd className="text-figure">{cell.value}</dd>
          <dd className="truncate text-small text-ink-subtle">{cell.note}</dd>
        </div>
      ))}
    </dl>
  );
}

const TICKS = [0, 25, 50, 75, 100];

function dotClass(candidate: CandidateRead, selected: boolean): string {
  if (selected) return "bg-primary outline outline-offset-2 outline-primary";
  if (candidate.status === "APPROVED") return "bg-success";
  if (candidate.status === "REJECTED")
    return "border border-ink-subtle bg-transparent";
  return "bg-ink";
}

// Every shortlisted seller on one 0-100 axis against the discovery line.
export function ThresholdStrip({
  run,
  selectedId,
}: {
  run: RunDetailResponse;
  selectedId: string | null;
}): React.JSX.Element {
  const scored = run.candidates
    .filter((c) => c.origin === "crm" && c.match_score != null)
    .sort((a, b) => (a.match_score ?? 0) - (b.match_score ?? 0));
  // Ranks within four points would collide, so every second one lifts a row.
  const rows = scored.map((c, i) => {
    const previous = scored[i - 1];
    return previous &&
      (c.match_score ?? 0) - (previous.match_score ?? 0) < 5 &&
      i % 2 === 1
      ? 1
      : 0;
  });
  const summary = scored
    .map((c) => `${c.seller_org_name} ${score(c.match_score)}`)
    .join(", ");

  return (
    <figure className="flex flex-col gap-xs rounded-lg border border-hairline bg-surface-1 px-md pt-sm pb-xs">
      <figcaption className="flex items-baseline justify-between gap-sm text-small text-ink-subtle">
        <span>Match scores</span>
        <span>
          Discovery line{" "}
          <span className="text-ink">{score(run.discovery_threshold)}</span>
        </span>
      </figcaption>
      <div
        role="img"
        aria-label={
          scored.length > 0
            ? `Scores: ${summary}. Discovery line at ${score(run.discovery_threshold)}.`
            : "No scores yet."
        }
        className="relative mx-[6px] h-[60px]"
      >
        <span
          aria-hidden
          className="absolute top-0 h-[42px] w-0 border-l border-dashed border-ink-subtle"
          style={{ left: `${String(run.discovery_threshold)}%` }}
        />
        <span
          aria-hidden
          className="absolute inset-x-0 top-[38px] h-px bg-hairline-strong"
        />
        {scored.map((c, i) => {
          const left = `${String(Math.max(0, Math.min(100, c.match_score ?? 0)))}%`;
          const selected = c.id === selectedId;
          return (
            <span key={c.id} aria-hidden>
              <span
                className={cn(
                  "absolute -translate-x-1/2 text-small",
                  selected ? "text-ink" : "text-ink-subtle",
                )}
                style={{ left, top: rows[i] === 1 ? "0px" : "16px" }}
              >
                {c.rank}
              </span>
              <span
                className={cn(
                  "absolute top-[34px] size-[9px] -translate-x-1/2 rounded-full",
                  dotClass(c, selected),
                )}
                style={{ left }}
              />
            </span>
          );
        })}
        {TICKS.map((tick) => (
          <span
            key={tick}
            aria-hidden
            className="absolute top-[46px] -translate-x-1/2 text-small leading-none text-ink-subtle"
            style={{ left: `${String(tick)}%` }}
          >
            {tick}
          </span>
        ))}
      </div>
    </figure>
  );
}
