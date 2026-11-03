import { Link } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";

export interface Parent {
  label: string;
  to: "/" | "/find-match" | "/settings";
}

// Title row: parent link, the serif h1, one line about the data, actions on the right.
export function PageHeader({
  parent,
  title,
  sub,
  actions,
}: {
  parent?: Parent;
  title: React.ReactNode;
  sub?: React.ReactNode;
  actions?: React.ReactNode;
}): React.JSX.Element {
  return (
    <header className="flex flex-col gap-md md:flex-row md:items-end md:justify-between">
      <div className="flex min-w-0 flex-col gap-xs">
        {parent && (
          <Link
            to={parent.to}
            className="-ml-[3px] inline-flex w-fit items-center gap-[2px] text-body text-ink-subtle transition-colors hover:text-ink"
          >
            <ChevronLeft aria-hidden className="size-4" strokeWidth={1.5} />
            {parent.label}
          </Link>
        )}
        <h1 className="font-serif text-[26px] text-balance md:text-title">
          {title}
        </h1>
        {sub && <div className="text-lead text-ink-muted">{sub}</div>}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-xs">
          {actions}
        </div>
      )}
    </header>
  );
}
