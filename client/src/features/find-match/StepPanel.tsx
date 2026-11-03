import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";

import { cn } from "@/lib/utils";

import { STEP_LABELS, type StepId, type StepState } from "./steps";

// One message in the run's timeline; the list is shaped so a future chat can reuse it.
export function StepPanel({
  id,
  state,
  summary,
  children,
}: {
  id: StepId;
  state: StepState;
  summary: React.ReactNode;
  children?: React.ReactNode;
}): React.JSX.Element {
  const contentId = useId();
  const collapsible = state === "done" || state === "skipped";
  const [expanded, setExpanded] = useState(false);
  const open = children !== undefined && (!collapsible || expanded);
  const lifted = state === "active" || state === "attention";

  const heading = (
    <>
      <span className="text-body-sm font-medium text-ink">
        {STEP_LABELS[id]}
      </span>
      <span className="min-w-0 flex-1 truncate text-body-sm text-ink-subtle">
        {summary}
      </span>
    </>
  );

  return (
    <li
      id={`step-${id}`}
      className={cn(
        "scroll-mt-32 rounded-lg border",
        lifted
          ? "border-hairline-strong bg-surface-2"
          : "border-hairline bg-surface-1",
        state === "upcoming" &&
          children === undefined &&
          "border-dashed bg-transparent",
      )}
    >
      <h2 className="flex min-h-12 items-center">
        {collapsible && children !== undefined ? (
          <button
            type="button"
            aria-expanded={expanded}
            aria-controls={contentId}
            onClick={() => {
              setExpanded((value) => !value);
            }}
            className="flex min-h-12 w-full cursor-pointer items-center gap-sm rounded-lg px-md text-left hover:bg-surface-2"
          >
            {heading}
            <ChevronDown
              aria-hidden
              className={cn(
                "size-4 shrink-0 text-ink-subtle transition-transform",
                expanded && "rotate-180",
              )}
            />
          </button>
        ) : (
          <span className="flex min-h-12 w-full items-center gap-sm px-md">
            {heading}
          </span>
        )}
      </h2>
      {open && (
        <div
          id={contentId}
          className="flex flex-col gap-md border-t border-hairline p-md"
        >
          {children}
        </div>
      )}
    </li>
  );
}
