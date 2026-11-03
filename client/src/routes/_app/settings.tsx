import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { setApiKey } from "@/lib/api-key";
import { forgetRecentRuns, useRecentRuns } from "@/lib/recent-runs";

export const Route = createFileRoute("/_app/settings")({
  component: SettingsPage,
});

function Row({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <section
      aria-labelledby={id}
      className="grid gap-md border-t border-hairline py-xl md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] md:gap-lg"
    >
      <div className="flex flex-col gap-xxs">
        <h2 id={id} className="text-section">
          {title}
        </h2>
        <p className="text-body text-ink-subtle">{description}</p>
      </div>
      <div className="rounded-lg border border-hairline bg-surface-1">
        {children}
      </div>
    </section>
  );
}

function Line({
  label,
  children,
  action,
}: {
  label: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-center justify-between gap-md border-b border-hairline px-md py-sm last:border-b-0">
      <div className="flex min-w-0 flex-col gap-[2px]">
        <p className="text-body font-medium text-ink">{label}</p>
        <p className="text-small text-ink-subtle">{children}</p>
      </div>
      {action}
    </div>
  );
}

// Clearing can't be undone, so it asks once inline before it happens.
function ClearRuns({ count }: { count: number }): React.JSX.Element {
  const [confirming, setConfirming] = useState(false);
  if (!confirming)
    return (
      <Button
        variant="secondary"
        disabled={count === 0}
        onClick={() => {
          setConfirming(true);
        }}
      >
        Clear list
      </Button>
    );
  return (
    <span className="flex gap-xs">
      <Button
        variant="tertiary"
        onClick={() => {
          setConfirming(false);
        }}
      >
        Cancel
      </Button>
      <Button
        variant="danger"
        onClick={() => {
          forgetRecentRuns();
          setConfirming(false);
        }}
      >
        Clear {count} {count === 1 ? "run" : "runs"}
      </Button>
    </span>
  );
}

function SettingsPage(): React.JSX.Element {
  const runs = useRecentRuns();
  return (
    <main
      id="main"
      tabIndex={-1}
      className="mx-auto flex w-full max-w-[1360px] flex-col gap-lg px-md py-lg outline-none md:px-xl md:py-xl"
    >
      <PageHeader
        title="Settings"
        sub="This browser's access to the toolkit, and what your decisions write."
      />
      <div className="flex flex-col">
        <Row
          id="access-title"
          title="Access key"
          description="Saved for this browser tab only. Approvals you make are recorded as made from the web app until sign-in with Slack arrives."
        >
          <Line
            label="Team access key"
            action={
              <Button
                variant="danger"
                onClick={() => {
                  setApiKey(null);
                }}
              >
                Forget key
              </Button>
            }
          >
            In use for this tab. Forgetting it asks for the key again.
          </Line>
        </Row>

        <Row
          id="decisions-title"
          title="Where decisions go"
          description="Every decision on a shortlist is saved to the run, so the CSV export carries it."
        >
          <Line label="Approve">
            Creates a Qualified deal in Attio for the buyer and seller, or
            promotes an existing Inbound one.
          </Line>
          <Line label="Reject">
            Recorded on the run only. Nothing is written to Attio.
          </Line>
          <Line label="Find more sellers">
            New sellers from Google Maps are added to the CRM, then join the
            shortlist for review.
          </Line>
        </Row>

        <Row
          id="runs-title"
          title="Recent runs"
          description="Runs you start are remembered on this device so you can come back to them. The runs themselves stay on the server."
        >
          <Line
            label={`${String(runs.length)} on this device`}
            action={<ClearRuns count={runs.length} />}
          >
            Clearing only removes them from this list.
          </Line>
        </Row>
      </div>
    </main>
  );
}
