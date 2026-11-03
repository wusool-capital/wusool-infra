import { score } from "@/lib/format";
import { cn } from "@/lib/utils";

// The run's own rule made visible: below the threshold mark, discovery takes over.
export function ScoreBar({
  value,
  threshold,
}: {
  value: number;
  threshold: number;
}): React.JSX.Element {
  const clamped = Math.max(0, Math.min(100, value));
  const below = value < threshold;
  const gap = Math.round(value - threshold);
  return (
    <div className="flex flex-col gap-xs">
      <div className="flex items-baseline justify-between gap-sm">
        <p className="text-figure">
          {score(value)}
          <span className="text-body text-ink-subtle"> /100 match</span>
        </p>
        <p className="text-small text-ink-subtle">
          {gap >= 0 ? "+" : "−"}
          {Math.abs(gap)} against the {score(threshold)} line
        </p>
      </div>
      <div
        role="meter"
        aria-label="Match score"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(value)}
        aria-valuetext={`${score(value)} of 100${below ? `, below the ${score(threshold)} discovery threshold` : ""}`}
        className="relative h-1 bg-hairline"
      >
        <span
          className={cn(
            "absolute inset-y-0 left-0",
            below ? "bg-ink-subtle" : "bg-primary",
          )}
          style={{ width: `${String(clamped)}%` }}
        />
        <span
          aria-hidden
          className="absolute -top-[4px] h-3 w-px bg-ink"
          style={{ left: `${String(threshold)}%` }}
        />
      </div>
    </div>
  );
}

// A row's score: the figure with a 2px bar under it, grey when under the line.
export function ScoreFigure({
  value,
  threshold,
}: {
  value: number | null | undefined;
  threshold: number;
}): React.JSX.Element {
  if (value == null)
    return <span className="text-body text-ink-subtle">—</span>;
  const below = value < threshold;
  return (
    <span className="flex w-14 flex-col items-end gap-[5px]">
      <span className={cn("text-body", below ? "text-ink-muted" : "text-ink")}>
        {score(value)}
      </span>
      <span aria-hidden className="relative h-[2px] w-full bg-hairline">
        <span
          className={cn(
            "absolute inset-y-0 left-0",
            below ? "bg-ink-subtle" : "bg-primary",
          )}
          style={{ width: `${String(Math.max(0, Math.min(100, value)))}%` }}
        />
      </span>
    </span>
  );
}
