import { cn } from "@/lib/utils";

// Two linked rings, buyer and seller: what "wusool" (connection) means, after the firm's own logo.
export function Mark({ className }: { className?: string }): React.JSX.Element {
  return (
    <svg
      viewBox="0 0 28 20"
      aria-hidden
      className={cn("h-5 w-7 text-primary", className)}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <circle cx="10" cy="10" r="7" />
      <circle cx="18" cy="10" r="7" />
    </svg>
  );
}
