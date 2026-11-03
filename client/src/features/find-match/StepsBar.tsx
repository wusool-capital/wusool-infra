import { Check } from "lucide-react";
import { useEffect, useRef } from "react";

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

// The whole sequence stays visible; the current step carries the one 1px accent line.
export function StepsBar({ steps }: { steps: StepStates }): React.JSX.Element {
  const list = useRef<HTMLOListElement>(null);
  const currentId = STEP_ORDER.find(
    (id) => steps[id] === "active" || steps[id] === "attention",
  );
  // On a phone the row scrolls; keep the current step in view.
  useEffect(() => {
    const ol = list.current;
    const li = ol?.querySelector<HTMLElement>("[data-current]");
    if (ol && li) ol.scrollLeft = li.offsetLeft - ol.offsetLeft - 16;
  }, [currentId]);
  return (
    <nav aria-label="Find-match progress" className="border-b border-hairline">
      <ol
        ref={list}
        className="-mb-px flex [scrollbar-width:none] gap-lg overflow-x-auto"
      >
        {STEP_ORDER.map((id) => {
          const state = steps[id];
          const current = state === "active" || state === "attention";
          return (
            <li
              key={id}
              aria-current={state === "active" ? "step" : undefined}
              data-current={current ? "" : undefined}
              className={cn(
                "flex shrink-0 items-center gap-[6px] border-b py-xs text-body whitespace-nowrap",
                current ? "border-primary" : "border-transparent",
                state === "active" && "text-ink",
                state === "attention" && "text-warning",
                state === "done" && "text-ink-muted",
                (state === "upcoming" || state === "skipped") &&
                  "text-ink-subtle",
              )}
            >
              {state === "done" && (
                <Check aria-hidden className="size-3.5" strokeWidth={2} />
              )}
              <span className={cn(state === "skipped" && "line-through")}>
                {STEP_LABELS[id]}
              </span>
              <span className="sr-only">, {STATE_TEXT[state]}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
