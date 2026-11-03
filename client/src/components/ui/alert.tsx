import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Status panels: same hue at 12% fill / 32% border (DESIGN.md App extensions).
const alertVariants = cva(
  "relative grid w-full grid-cols-[0_1fr] items-start gap-y-xxs rounded-lg border px-md py-sm text-body-sm has-[>svg]:grid-cols-[16px_1fr] has-[>svg]:gap-x-sm [&>svg]:mt-[3px] [&>svg]:size-4",
  {
    variants: {
      tone: {
        neutral:
          "border-hairline bg-surface-1 text-ink [&>svg]:text-ink-subtle",
        warning:
          "border-warning/32 bg-warning/12 text-ink [&>svg]:text-warning",
        danger: "border-danger/32 bg-danger/12 text-ink [&>svg]:text-danger",
        success:
          "border-success/32 bg-success/12 text-ink [&>svg]:text-success",
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
      className={cn("col-start-2 font-medium text-ink", className)}
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
      className={cn("col-start-2 grid gap-xxs text-ink-muted", className)}
      {...props}
    />
  );
}

export { Alert, AlertTitle, AlertDescription };
