import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { errorReport } from "@/lib/error-report";

const RESET_MS = 2000;

// Copies an error with its page and time, so an advisor can paste it to the team.
export function CopyErrorButton({
  message,
}: {
  message: string;
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

  return (
    <Button
      type="button"
      size="sm"
      variant="tertiary"
      className="self-start"
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
      <span aria-live="polite">
        {state === "copied"
          ? "Copied"
          : state === "failed"
            ? "Couldn't copy"
            : "Copy error"}
      </span>
    </Button>
  );
}
