import { createFileRoute, Outlet } from "@tanstack/react-router";

import { AuthGate } from "@/components/AuthGate";
import { BottomBar, Rail } from "@/components/Rail";

export const Route = createFileRoute("/_app")({
  component: AppLayout,
});

function AppLayout(): React.JSX.Element {
  return (
    <AuthGate>
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-surface-3 px-md py-xs text-body focus:not-sr-only focus:fixed focus:top-xs focus:left-xs"
      >
        Skip to content
      </a>
      <div className="flex h-full">
        <div className="hidden shrink-0 md:block">
          <Rail />
        </div>
        <div className="flex min-w-0 flex-1 flex-col overflow-y-auto pb-16 md:pb-0">
          <Outlet />
        </div>
        <div className="md:hidden">
          <BottomBar />
        </div>
      </div>
    </AuthGate>
  );
}
