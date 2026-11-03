import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Status tags: a dark tint of the hue with the hue as text; neutral states stay grey.
const badgeVariants = cva(
  "inline-flex h-5 w-fit flex-none items-center gap-[6px] rounded-xs px-[6px] text-small font-medium whitespace-nowrap",
  {
    variants: {
      tone: {
        neutral: "bg-surface-3 text-ink-muted",
        running:
          "bg-surface-3 text-ink-muted before:size-[6px] before:animate-pulse before:rounded-full before:bg-primary before:content-['']",
        success: "bg-success-tint text-success",
        warning: "bg-warning-tint text-warning",
        danger: "bg-danger-tint text-danger",
        plain: "bg-transparent px-0 text-ink-subtle",
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
