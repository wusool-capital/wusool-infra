import * as React from "react";

import { cn } from "@/lib/utils";

// DESIGN.md text-input: surface-1, rounded-md, 8px 12px; ≥44px tap height.
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "min-h-11 w-full min-w-0 rounded-md border border-hairline bg-surface-1 px-sm py-xs text-body text-ink transition-colors placeholder:text-ink-subtle hover:border-hairline-strong focus-visible:border-hairline-strong disabled:cursor-not-allowed disabled:text-ink-tertiary aria-invalid:border-danger",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
