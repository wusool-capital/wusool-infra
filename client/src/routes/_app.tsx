import { createFileRoute, Outlet } from "@tanstack/react-router";
import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { ApiKeyGate } from "@/components/ApiKeyGate";
import { ShellContext } from "@/components/shell-context";
import { Sidebar } from "@/components/Sidebar";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/_app")({
  component: AppLayout,
});

function AppLayout(): React.JSX.Element {
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === "Escape") setNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [navOpen]);

  return (
    <ApiKeyGate>
      <ShellContext
        value={{
          openNav: () => {
            setNavOpen(true);
          },
        }}
      >
        <a
          href="#main"
          className="sr-only z-50 rounded-md bg-surface-3 px-md py-xs text-body-sm focus:not-sr-only focus:fixed focus:top-xs focus:left-xs"
        >
          Skip to content
        </a>
        <div className="flex h-full">
          <aside className="hidden w-[240px] shrink-0 border-r border-hairline md:block">
            <Sidebar />
          </aside>
          {navOpen && (
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Navigation"
              className="fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-canvas md:hidden"
            >
              <Button
                variant="tertiary"
                size="icon"
                aria-label="Close navigation"
                className="absolute top-xs right-xs"
                onClick={() => {
                  setNavOpen(false);
                }}
              >
                <X aria-hidden />
              </Button>
              <Sidebar
                onNavigate={() => {
                  setNavOpen(false);
                }}
              />
            </div>
          )}
          <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
            <Outlet />
          </div>
        </div>
      </ShellContext>
    </ApiKeyGate>
  );
}
