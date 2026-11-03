import { createFileRoute } from "@tanstack/react-router";

import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/ui/button";
import { setApiKey } from "@/lib/api-key";

export const Route = createFileRoute("/_app/settings")({
  component: SettingsPage,
});

function SettingsPage(): React.JSX.Element {
  return (
    <>
      <TopBar crumbs={[{ label: "Tools", to: "/" }, { label: "Settings" }]} />
      <main className="mx-auto flex w-full max-w-[760px] flex-col gap-xl px-md py-xl md:px-xl">
        <h1 className="text-headline">Settings</h1>
        <section
          aria-labelledby="access-title"
          className="grid gap-md rounded-lg border border-hairline bg-surface-1 p-lg md:grid-cols-[1fr_auto] md:items-center"
        >
          <div className="flex flex-col gap-xxs">
            <h2 id="access-title" className="text-body font-medium">
              Access key
            </h2>
            <p className="text-body-sm text-ink-subtle">
              Saved for this browser tab only. Approvals you make are recorded
              as made from the web app until sign-in with Slack arrives.
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => {
              setApiKey(null);
            }}
          >
            Forget key
          </Button>
        </section>
      </main>
    </>
  );
}
