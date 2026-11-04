import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { errorReport } from "@/lib/error-report";
import { cn } from "@/lib/utils";

const RESET_MS = 2000;

// Copies an error with its page and time, so an advisor can paste it to the team.
export function CopyErrorButton({
  message,
  className,
}: {
  message: string;
  className?: string;
}): React.JSX.Element {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (state === "idle") return;
    const timer = setTimeout(() => {
      setState("idle");
    }, RESET_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [state]);

  const label =
    state === "copied"
      ? "Copied"
      : state === "failed"
        ? "Couldn't copy"
        : "Copy error";
  return (
    <Button
      type="button"
      size="icon"
      variant="tertiary"
      aria-label={label}
      title={label}
      className={cn("size-8 shrink-0", className)}
      onClick={() => {
        navigator.clipboard
          .writeText(errorReport(message))
          .then(() => {
            setState("copied");
          })
          .catch(() => {
            setState("failed");
          });
      }}
    >
      {state === "copied" ? <Check aria-hidden /> : <Copy aria-hidden />}
      <span aria-live="polite" className="sr-only">
        {state === "idle" ? "" : label}
      </span>
    </Button>
  );
}
