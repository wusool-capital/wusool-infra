import { cn } from "@/lib/utils";

// Wusool Capital's own mark; its white tile keeps the midnight logo legible on the dark ground.
export function Mark({ className }: { className?: string }): React.JSX.Element {
  return (
    <img
      src={`${import.meta.env.BASE_URL}logo.png`}
      alt=""
      aria-hidden
      width={32}
      height={32}
      className={cn("size-8 rounded-xs", className)}
    />
  );
}
