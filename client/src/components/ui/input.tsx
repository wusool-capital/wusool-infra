import * as React from "react";

import { cn } from "@/lib/utils";

// Fields sit darker than the ground with a control-strength edge; ≥44px tap height.
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-11 w-full min-w-0 rounded-md border border-hairline-strong bg-surface-1 px-sm text-lead text-ink transition-colors placeholder:text-ink-subtle hover:border-hairline-tertiary focus-visible:border-primary focus-visible:outline-none disabled:cursor-not-allowed disabled:text-ink-tertiary aria-invalid:border-danger",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
