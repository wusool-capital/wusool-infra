import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// In-block notices: colour only on the icon and a 2px leading edge, text stays ink.
const alertVariants = cva(
  "relative grid w-full grid-cols-[0_minmax(0,1fr)] items-start gap-y-xxs rounded-lg border-l-2 bg-surface-2 py-sm pr-md pl-sm text-body has-[>svg]:grid-cols-[16px_minmax(0,1fr)] has-[>svg]:gap-x-sm [&>svg]:mt-[2px] [&>svg]:size-4",
  {
    variants: {
      tone: {
        neutral: "border-hairline-strong [&>svg]:text-ink-subtle",
        warning: "border-warning [&>svg]:text-warning",
        danger: "border-danger [&>svg]:text-danger",
        success: "border-success [&>svg]:text-success",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  },
);

function Alert({
  className,
  tone,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      role="alert"
      className={cn(alertVariants({ tone }), className)}
      {...props}
    />
  );
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        "col-start-2 font-medium [overflow-wrap:anywhere] text-ink",
        className,
      )}
      {...props}
    />
  );
}

function AlertDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        "col-start-2 grid gap-xxs [overflow-wrap:anywhere] text-ink-muted",
        className,
      )}
      {...props}
    />
  );
}

export { Alert, AlertTitle, AlertDescription };
