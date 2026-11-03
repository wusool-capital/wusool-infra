import { Link } from "@tanstack/react-router";
import {
  KeyRound,
  LayoutGrid,
  MessageSquare,
  Plus,
  Settings,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { setApiKey } from "@/lib/api-key";
import { relativeTime } from "@/lib/format";
import { useRecentRuns } from "@/lib/recent-runs";

const NAV = [
  { to: "/", label: "Tools", icon: LayoutGrid },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

const navItem =
  "relative flex min-h-9 items-center gap-sm rounded-md px-sm text-body-sm text-ink-subtle transition-colors hover:bg-surface-1 hover:text-ink";
// The lavender bar is the "active nav item" use DESIGN.md allows.
const navActive =
  "bg-surface-1 text-ink before:absolute before:inset-y-xs before:left-0 before:w-[2px] before:rounded-full before:bg-primary before:content-['']";

export function Sidebar({
  onNavigate,
}: {
  onNavigate?: () => void;
}): React.JSX.Element {
  const runs = useRecentRuns();
  return (
    <div className="flex h-full flex-col gap-lg bg-canvas px-sm py-md">
      <Link
        to="/"
        onClick={onNavigate}
        className="flex items-center gap-xs px-xs text-body font-semibold tracking-[-0.2px] text-ink"
      >
        <span
          aria-hidden
          className="grid size-6 place-items-center rounded-sm bg-primary"
        >
          <span className="size-2 rounded-full bg-on-primary" />
        </span>
        Wusool
      </Link>

      <Button asChild className="w-full justify-start">
        <Link to="/find-match" onClick={onNavigate}>
          <Plus aria-hidden />
          New run
        </Link>
      </Button>

      <nav aria-label="Main">
        <ul className="flex flex-col gap-xxs">
          {NAV.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <Link
                to={to}
                onClick={onNavigate}
                className={navItem}
                activeProps={{ className: navActive }}
                activeOptions={{ exact: to === "/" }}
              >
                <Icon aria-hidden className="size-4" />
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <section
        aria-labelledby="recent-runs"
        className="flex min-h-0 flex-1 flex-col gap-xs"
      >
        <h2 id="recent-runs" className="px-sm text-eyebrow text-ink-subtle">
          Recent runs
        </h2>
        {runs.length === 0 ? (
          <p className="px-sm text-caption text-ink-subtle">
            Runs you start appear here.
          </p>
        ) : (
          <ul className="-mx-xxs flex min-h-0 flex-col gap-[2px] overflow-y-auto px-xxs">
            {runs.map((run) => (
              <li key={run.runId}>
                <Link
                  to="/runs/$runId"
                  params={{ runId: run.runId }}
                  onClick={onNavigate}
                  className={`${navItem} justify-between`}
                  activeProps={{ className: "bg-surface-1 text-ink" }}
                >
                  <span className="truncate">{run.buyerName}</span>
                  <span className="shrink-0 text-caption text-ink-subtle">
                    {relativeTime(run.startedAt)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Reserved for the assistant chat (later). */}
      <div
        aria-disabled
        className="flex min-h-9 items-center gap-sm rounded-md border border-dashed border-hairline px-sm text-body-sm text-ink-subtle"
      >
        <MessageSquare aria-hidden className="size-4" />
        Assistant
        <span className="ml-auto text-caption">Soon</span>
      </div>

      <button
        type="button"
        onClick={() => {
          setApiKey(null);
        }}
        className={`${navItem} w-full cursor-pointer`}
      >
        <KeyRound aria-hidden className="size-4" />
        Forget access key
      </button>
    </div>
  );
}
