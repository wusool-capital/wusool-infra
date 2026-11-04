import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

import {
  STEP_LABELS,
  STEP_ORDER,
  type StepState,
  type StepStates,
} from "./steps";

const STATE_TEXT: Record<StepState, string> = {
  done: "Done",
  active: "Now",
  upcoming: "Next",
  skipped: "Skipped",
  attention: "Needs you",
};

const SEGMENT: Record<StepState, string> = {
  done: "border-primary",
  active: "border-primary",
  attention: "border-warning",
  upcoming: "border-hairline-strong",
  skipped: "border-dashed border-hairline-strong",
};

// A progress track, not tabs: filled segments and state words say how far the run has got.
export function StepsBar({ steps }: { steps: StepStates }): React.JSX.Element {
  const list = useRef<HTMLOListElement>(null);
  const currentId = STEP_ORDER.find(
    (id) => steps[id] === "active" || steps[id] === "attention",
  );
  // On a phone the track scrolls; keep the current step in view.
  useEffect(() => {
    const ol = list.current;
    const li = ol?.querySelector<HTMLElement>("[data-current]");
    if (ol && li) ol.scrollLeft = li.offsetLeft - ol.offsetLeft - 16;
  }, [currentId]);
  return (
    <section aria-label="Run progress">
      <ol
        ref={list}
        className="grid [scrollbar-width:none] auto-cols-[minmax(104px,1fr)] grid-flow-col gap-xs overflow-x-auto"
      >
        {STEP_ORDER.map((id, index) => {
          const state = steps[id];
          const current = state === "active" || state === "attention";
          return (
            <li
              key={id}
              aria-current={state === "active" ? "step" : undefined}
              data-current={current ? "" : undefined}
              className={cn(
                "flex cursor-default flex-col gap-[6px] border-t-2 pt-xs select-none",
                SEGMENT[state],
              )}
            >
              <span
                className={cn(
                  "flex items-baseline gap-[6px] text-body whitespace-nowrap",
                  current || state === "done" ? "text-ink" : "text-ink-subtle",
                  state === "skipped" && "line-through",
                )}
              >
                <span className="text-small text-ink-subtle">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {STEP_LABELS[id]}
              </span>
              <span
                className={cn(
                  "text-small",
                  state === "attention" ? "text-warning" : "text-ink-subtle",
                  state === "active" && "text-primary",
                )}
              >
                {STATE_TEXT[state]}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
