import { createFileRoute, Outlet } from "@tanstack/react-router";

import { AuthGate } from "@/components/AuthGate";
import { BottomBar, Rail } from "@/components/Rail";
import { ScrollArea } from "@/components/ui/scroll-area";

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
        <ScrollArea
          className="min-w-0 flex-1"
          viewportClassName="[&>div]:h-full"
        >
          <div className="flex h-full flex-col">
            <Outlet />
            {/* Room for the fixed bottom bar, after the content even when a page overflows. */}
            <div aria-hidden className="h-16 shrink-0 md:hidden" />
          </div>
        </ScrollArea>
        <div className="md:hidden">
          <BottomBar />
        </div>
      </div>
    </AuthGate>
  );
}
