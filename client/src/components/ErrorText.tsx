import { CopyErrorButton } from "@/components/CopyErrorButton";
import { cn } from "@/lib/utils";

// An inline failure: wraps long server text instead of overflowing, copy at its top right.
export function ErrorText({
  message,
  className,
}: {
  message: string;
  className?: string;
}): React.JSX.Element {
  return (
    <div
      role="alert"
      className={cn(
        "flex w-full min-w-0 items-start justify-between gap-sm",
        className,
      )}
    >
      <p className="min-w-0 text-body [overflow-wrap:anywhere] text-danger">
        {message}
      </p>
      <CopyErrorButton message={message} />
    </div>
  );
}
