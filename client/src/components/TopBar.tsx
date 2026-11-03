import { Link } from "@tanstack/react-router";
import { Menu } from "lucide-react";
import { Fragment } from "react";

import { Button } from "@/components/ui/button";
import { useShell } from "@/components/shell-context";

export interface Crumb {
  label: string;
  to?: "/" | "/find-match" | "/settings";
}

export function TopBar({
  crumbs,
  trailing,
}: {
  crumbs: Crumb[];
  trailing?: React.ReactNode;
}): React.JSX.Element {
  const { openNav } = useShell();
  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-sm border-b border-hairline bg-canvas px-md md:px-lg">
      <Button
        variant="tertiary"
        size="icon"
        className="md:hidden"
        aria-label="Open navigation"
        onClick={openNav}
      >
        <Menu aria-hidden />
      </Button>
      <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
        <ol className="flex min-w-0 items-center gap-xs text-body-sm">
          {crumbs.map((crumb, index) => {
            const last = index === crumbs.length - 1;
            return (
              <Fragment key={`${crumb.label}-${String(index)}`}>
                {index > 0 && (
                  <li aria-hidden className="text-ink-tertiary">
                    /
                  </li>
                )}
                <li className="min-w-0 truncate">
                  {crumb.to !== undefined && !last ? (
                    <Link
                      to={crumb.to}
                      className="text-ink-subtle hover:text-ink"
                    >
                      {crumb.label}
                    </Link>
                  ) : (
                    <span
                      aria-current={last ? "page" : undefined}
                      className={last ? "text-ink" : "text-ink-subtle"}
                    >
                      {crumb.label}
                    </span>
                  )}
                </li>
              </Fragment>
            );
          })}
        </ol>
      </nav>
      {trailing}
    </header>
  );
}
