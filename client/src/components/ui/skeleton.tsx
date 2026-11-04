import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("rounded-xs bg-surface-3", className)}
      {...props}
    />
  );
}

export { Skeleton };
