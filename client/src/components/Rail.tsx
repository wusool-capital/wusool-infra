import { Link, useRouterState } from "@tanstack/react-router";
import { LogOut, Plus, Settings, Waypoints } from "lucide-react";
import { Tooltip } from "radix-ui";

import { Mark } from "@/components/Mark";
import { displayName, useCurrentUser, useSignOut } from "@/lib/session";
import { cn } from "@/lib/utils";

type Destination = "/" | "/find-match" | "/settings";

const NAV: {
  to: Destination;
  label: string;
  icon: typeof Plus;
  matches: (path: string) => boolean;
}[] = [
  {
    to: "/",
    label: "Find match",
    icon: Waypoints,
    matches: (p) => p === "/" || p.startsWith("/runs"),
  },
  {
    to: "/find-match",
    label: "New run",
    icon: Plus,
    matches: (p) => p.startsWith("/find-match"),
  },
  {
    to: "/settings",
    label: "Settings",
    icon: Settings,
    matches: (p) => p.startsWith("/settings"),
  },
];

function usePath(): string {
  return useRouterState({ select: (s) => s.location.pathname });
}

const railItem =
  "relative grid size-10 place-items-center rounded-md text-ink-subtle transition-colors hover:bg-surface-2 hover:text-ink";
// The one selection mark: a 1px accent line on the rail's edge.
const railActive =
  "text-ink after:absolute after:inset-y-[6px] after:-right-[9px] after:w-px after:bg-primary after:content-['']";

function Tip({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="right"
          sideOffset={10}
          className="z-50 rounded-xs bg-surface-4 px-xs py-[5px] text-small text-ink shadow-float"
        >
          {label}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

function RailLink({
  item,
  path,
}: {
  item: (typeof NAV)[number];
  path: string;
}): React.JSX.Element {
  const { to, label, icon: Icon, matches } = item;
  return (
    <Tip label={label}>
      <Link
        to={to}
        aria-label={label}
        aria-current={matches(path) ? "page" : undefined}
        className={cn(railItem, matches(path) && railActive)}
      >
        <Icon aria-hidden className="size-[18px]" strokeWidth={1.5} />
      </Link>
    </Tip>
  );
}

export function Rail(): React.JSX.Element {
  const path = usePath();
  const user = useCurrentUser();
  const signOut = useSignOut();
  return (
    <Tooltip.Provider delayDuration={200}>
      <nav
        aria-label="Main"
        className="flex h-full w-14 flex-col items-center gap-xs border-r border-hairline bg-canvas py-sm"
      >
        <Link
          to="/"
          aria-label="Wusool Toolkit home"
          className="mb-sm grid size-10 place-items-center"
        >
          <Mark />
        </Link>
        {NAV.filter((item) => item.to !== "/settings").map((item) => (
          <RailLink key={item.to} item={item} path={path} />
        ))}
        <div className="mt-auto flex flex-col items-center gap-xs">
          {NAV.filter((item) => item.to === "/settings").map((item) => (
            <RailLink key={item.to} item={item} path={path} />
          ))}
          <Tip label={`Sign out · ${displayName(user)}`}>
            <button
              type="button"
              aria-label={`Sign out ${displayName(user)}`}
              onClick={() => {
                void signOut();
              }}
              className={cn(railItem, "cursor-pointer")}
            >
              <LogOut aria-hidden className="size-[18px]" strokeWidth={1.5} />
            </button>
          </Tip>
        </div>
      </nav>
    </Tooltip.Provider>
  );
}

// The phone's navigation: the rail's destinations as a labelled bottom bar.
export function BottomBar(): React.JSX.Element {
  const path = usePath();
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 grid h-16 grid-cols-3 border-t border-hairline bg-canvas pb-[env(safe-area-inset-bottom)]"
    >
      {NAV.map(({ to, label, icon: Icon, matches }) => (
        <Link
          key={to}
          to={to}
          aria-current={matches(path) ? "page" : undefined}
          className={cn(
            "relative flex flex-col items-center justify-center gap-[3px] text-small text-ink-subtle",
            matches(path) &&
              "text-ink before:absolute before:inset-x-[30%] before:top-[-1px] before:h-px before:bg-primary before:content-['']",
          )}
        >
          <Icon aria-hidden className="size-5" strokeWidth={1.5} />
          {label}
        </Link>
      ))}
    </nav>
  );
}
