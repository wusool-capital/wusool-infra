import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { displayName, useCurrentUser, useSignOut } from "@/lib/session";
import {
  EXPORT_FIELDS,
  EXPORT_PRESETS,
  type ExportPreset,
  matchingPreset,
  setExportFields,
  useExportFields,
} from "@/lib/export-fields";
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

// A preset fills the ticks; editing any tick makes it a custom set. At least one column stays.
function ExportFields(): React.JSX.Element {
  const fields = useExportFields();
  const preset = matchingPreset(fields);
  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap items-center gap-xs border-b border-hairline px-md py-sm">
        <span className="mr-xs text-small text-ink-subtle">Preset</span>
        {(Object.keys(EXPORT_PRESETS) as ExportPreset[]).map((id) => (
          <Button
            key={id}
            size="sm"
            variant={preset === id ? "default" : "secondary"}
            aria-pressed={preset === id}
            onClick={() => {
              setExportFields(EXPORT_PRESETS[id].fields);
            }}
          >
            {EXPORT_PRESETS[id].label}
          </Button>
        ))}
        {preset === null && (
          <span className="text-small text-ink-subtle">
            Custom · {fields.length} of {EXPORT_FIELDS.length}
          </span>
        )}
      </div>
      <fieldset className="grid gap-x-md px-md py-xs sm:grid-cols-2">
        <legend className="sr-only">Columns in the CSV</legend>
        {EXPORT_FIELDS.map((field) => {
          const checked = fields.includes(field.id);
          const last = checked && fields.length === 1;
          return (
            <label
              key={field.id}
              className="flex min-h-10 cursor-pointer items-center gap-sm text-body text-ink has-disabled:cursor-not-allowed has-disabled:text-ink-subtle"
            >
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={checked}
                disabled={last}
                onChange={() => {
                  setExportFields(
                    checked
                      ? fields.filter((id) => id !== field.id)
                      : [...fields, field.id],
                  );
                }}
              />
              {field.label}
            </label>
          );
        })}
      </fieldset>
    </div>
  );
}

function AccessLine(): React.JSX.Element {
  const user = useCurrentUser();
  const signOut = useSignOut();
  const viaKey = user === null || user.via === "key";
  return (
    <Line
      label={displayName(user)}
      action={
        <Button
          variant="danger"
          onClick={() => {
            void signOut();
          }}
        >
          Sign out
        </Button>
      }
    >
      {viaKey
        ? "Using the shared access key for this tab. Decisions are recorded as the web app, not a person."
        : "Signed in with Slack."}
    </Line>
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
          title="Signed in"
          description="Runs you start and decisions you make are recorded under your Slack account, the same as /find-match in Slack. You stay signed in for 30 days after your last visit."
        >
          <AccessLine />
        </Row>

        <Row
          id="decisions-title"
          title="Where decisions go"
          description="Every decision on a shortlist is saved to the run, so the CSV export carries it."
        >
          <Line label="Approve">
            Creates a Qualified deal in Attio for the buyer and seller, or
            promotes an existing Lead one.
          </Line>
          <Line label="Reject">
            Recorded on the run only. Nothing is written to Attio.
          </Line>
          <Line label="Find more sellers">
            New sellers from Google Maps are added to the CRM, then join the
            shortlist for review. Runs on its own when every score is low, and
            can be started on any finished run.
          </Line>
        </Row>

        <Row
          id="export-title"
          title="CSV export"
          description="Which columns Download CSV includes. Business keeps what a deal team reads; Everything adds IDs, links and confidence. Saved on this device."
        >
          <ExportFields />
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
