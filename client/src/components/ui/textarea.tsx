import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "field-sizing-content min-h-28 w-full rounded-md border border-hairline bg-surface-1 px-sm py-xs text-body text-ink transition-colors placeholder:text-ink-subtle hover:border-hairline-strong focus-visible:border-hairline-strong disabled:cursor-not-allowed disabled:text-ink-tertiary aria-invalid:border-danger",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
