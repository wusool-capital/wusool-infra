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
  return (
    <div className="flex items-center gap-sm">
      <div
        role="meter"
        aria-label="Match score"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(value)}
        aria-valuetext={`${score(value)} of 100${below ? `, below the ${score(threshold)} discovery threshold` : ""}`}
        className="relative h-[6px] flex-1 rounded-full bg-surface-4"
      >
        <span
          className={cn(
            "absolute inset-y-0 left-0 rounded-full",
            below ? "bg-warning" : "bg-success",
          )}
          style={{ width: `${String(clamped)}%` }}
        />
        <span
          aria-hidden
          title={`Discovery threshold ${score(threshold)}`}
          className="absolute -top-[3px] h-[12px] w-[2px] rounded-full bg-ink-muted"
          style={{ left: `calc(${String(threshold)}% - 1px)` }}
        />
      </div>
      <span className="w-8 text-right text-body-sm font-medium text-ink tabular-nums">
        {score(value)}
      </span>
    </div>
  );
}
