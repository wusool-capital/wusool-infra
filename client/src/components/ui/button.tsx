import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";

import { cn } from "@/lib/utils";

// Square like wusoolcapital.com's buttons; gulf blue fill is kept to one action per screen.
const buttonVariants = cva(
  "inline-flex h-9 shrink-0 cursor-pointer items-center justify-center gap-xs rounded-md px-sm text-body font-medium whitespace-nowrap transition-[background-color,border-color,color,transform] duration-150 select-none active:translate-y-px disabled:pointer-events-none disabled:text-ink-subtle [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-on-primary hover:bg-primary-hover disabled:bg-surface-3",
        secondary:
          "border border-hairline-strong bg-transparent text-ink hover:border-hairline-tertiary hover:bg-surface-2",
        tertiary:
          "bg-transparent text-ink-muted hover:bg-surface-2 hover:text-ink",
        danger:
          "border border-hairline-strong bg-transparent text-ink hover:border-danger/60 hover:bg-danger-tint hover:text-danger",
        link: "h-auto px-0 text-ink underline decoration-hairline-tertiary underline-offset-4 hover:decoration-ink",
      },
      size: {
        default: "",
        sm: "h-8 px-[10px]",
        lg: "h-11 px-md",
        icon: "size-9 px-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }) {
  const Comp = asChild ? Slot.Root : "button";

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
