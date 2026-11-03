import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";

import { cn } from "@/lib/utils";

// DESIGN.md button-*: rounded-md, 8px 14px, `button` type. Never pill-shaped.
const buttonVariants = cva(
  "inline-flex min-h-10 shrink-0 cursor-pointer items-center justify-center gap-xs rounded-md px-[14px] py-xs text-button whitespace-nowrap transition-colors outline-none disabled:pointer-events-none disabled:text-ink-tertiary [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-on-primary hover:bg-primary-hover active:bg-primary-focus disabled:bg-surface-2",
        secondary:
          "border border-hairline bg-surface-1 text-ink hover:border-hairline-strong hover:bg-surface-2",
        tertiary: "bg-transparent text-ink hover:bg-surface-1",
        danger:
          "border border-danger/30 bg-transparent text-danger hover:bg-danger/12",
        link: "min-h-0 px-0 py-0 text-primary-hover underline-offset-4 hover:underline",
      },
      size: {
        default: "",
        sm: "min-h-8 px-sm py-xxs",
        icon: "size-10 px-0 py-0",
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
