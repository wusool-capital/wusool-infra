import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "field-sizing-content min-h-28 w-full rounded-md border border-hairline-strong bg-surface-1 px-sm py-[10px] text-lead text-ink transition-colors placeholder:text-ink-subtle hover:border-hairline-tertiary focus-visible:border-primary focus-visible:outline-none disabled:cursor-not-allowed disabled:text-ink-tertiary aria-invalid:border-danger",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
