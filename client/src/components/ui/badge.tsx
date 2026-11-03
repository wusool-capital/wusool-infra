import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// DESIGN.md status-badge + App extensions status tags: pill, caption, leading dot.
const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-[6px] rounded-full bg-surface-2 px-xs py-[2px] text-caption whitespace-nowrap before:size-[6px] before:rounded-full before:content-['']",
  {
    variants: {
      tone: {
        neutral: "text-ink-subtle before:bg-ink-subtle",
        running: "text-ink-muted before:animate-pulse before:bg-ink-muted",
        success: "text-ink-muted before:bg-success",
        warning: "text-warning before:bg-warning",
        danger: "text-danger before:bg-danger",
        plain: "text-ink-subtle before:hidden",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  },
);

function Badge({
  className,
  tone,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ tone }), className)}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
