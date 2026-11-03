import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

import {
  STEP_LABELS,
  STEP_ORDER,
  type StepState,
  type StepStates,
} from "./steps";

const STATE_TEXT: Record<StepState, string> = {
  done: "done",
  active: "current",
  upcoming: "not started",
  skipped: "skipped",
  attention: "needs attention",
};

// The whole sequence stays visible so the advisor always knows where the run is.
export function StepsBar({ steps }: { steps: StepStates }): React.JSX.Element {
  const position = STEP_ORDER.findIndex(
    (id) => steps[id] === "active" || steps[id] === "attention",
  );
  const current = position === -1 ? STEP_ORDER.length - 1 : position;
  const currentId = STEP_ORDER[current] ?? "export";

  return (
    <nav
      aria-label="Find-match progress"
      className="border-b border-hairline bg-canvas"
    >
      <p className="px-md pt-sm text-caption text-ink-subtle md:hidden">
        Step {current + 1} of {STEP_ORDER.length} · {STEP_LABELS[currentId]}
      </p>
      <ol className="flex gap-xxs px-md py-sm md:gap-xs md:px-lg">
        {STEP_ORDER.map((id) => {
          const state = steps[id];
          return (
            <li
              key={id}
              aria-current={state === "active" ? "step" : undefined}
              className="flex min-w-0 flex-1 flex-col gap-xs"
            >
              <span
                aria-hidden
                className={cn(
                  "h-[3px] rounded-full",
                  state === "done" && "bg-ink-muted",
                  state === "active" && "bg-ink",
                  state === "attention" && "bg-warning",
                  (state === "upcoming" || state === "skipped") &&
                    "bg-surface-4",
                )}
              />
              <span
                aria-hidden
                className={cn(
                  "hidden min-w-0 items-center gap-xxs truncate text-caption md:flex",
                  state === "active" && "text-ink",
                  state === "done" && "text-ink-muted",
                  state === "attention" && "text-warning",
                  (state === "upcoming" || state === "skipped") &&
                    "text-ink-subtle",
                  state === "skipped" && "line-through",
                )}
              >
                {state === "done" && (
                  <Check aria-hidden className="size-3 shrink-0" />
                )}
                <span className="truncate">{STEP_LABELS[id]}</span>
              </span>
              <span className="sr-only">
                {STEP_LABELS[id]}, {STATE_TEXT[state]}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
