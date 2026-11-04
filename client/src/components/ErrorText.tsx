import { CopyErrorButton } from "@/components/CopyErrorButton";
import { cn } from "@/lib/utils";

// An inline failure: wraps long server text instead of overflowing, with a copy button.
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
      className={cn("flex min-w-0 flex-col items-start gap-xxs", className)}
    >
      <p className="text-body [overflow-wrap:anywhere] text-danger">
        {message}
      </p>
      <CopyErrorButton message={message} />
    </div>
  );
}
