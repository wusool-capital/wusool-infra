import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, Search } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { TOOLS } from "@/features/tools";
import { useGetMatchRun } from "@/gen/hooks/useGetMatchRun";
import { relativeTime } from "@/lib/format";
import { type RecentRun, useRecentRuns } from "@/lib/recent-runs";

export const Route = createFileRoute("/_app/")({
  component: HomePage,
});

function HomePage(): React.JSX.Element {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const trimmed = query.trim();
  const runs = useRecentRuns();
  const slackTools = TOOLS.filter((tool) => !tool.web);

  return (
    <main
      id="main"
      tabIndex={-1}
      className="mx-auto flex w-full max-w-[1360px] flex-col gap-xl px-md py-lg outline-none md:px-xl md:py-xl"
    >
      <PageHeader
        title="Find match"
        sub="Score the CRM's sellers against a buyer's mandate, then approve a reasoned shortlist into Attio."
      />

      <form
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          if (trimmed.length < 2) return;
          void navigate({ to: "/find-match", search: { q: trimmed } });
        }}
        className="flex max-w-[880px] flex-col gap-xs sm:flex-row"
      >
        <label htmlFor="home-buyer" className="sr-only">
          Buyer name
        </label>
        <div className="relative flex-1">
          <Search
            aria-hidden
            strokeWidth={1.5}
            className="pointer-events-none absolute top-1/2 left-sm size-[18px] -translate-y-1/2 text-ink-subtle"
          />
          <input
            id="home-buyer"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
            name="buyer"
            placeholder="Which buyer are we matching? Type a name…"
            autoComplete="off"
            className="h-12 w-full rounded-md border border-hairline-strong bg-surface-1 pr-sm pl-[42px] text-lead text-ink transition-colors outline-none placeholder:text-ink-subtle hover:border-hairline-tertiary focus-visible:border-primary"
          />
        </div>
        <Button
          type="submit"
          size="lg"
          className="h-12"
          disabled={trimmed.length < 2}
        >
          Find buyer
          <ArrowRight aria-hidden />
        </Button>
      </form>

      <div className="grid items-start gap-xl lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-lg">
        <section
          aria-labelledby="recent-title"
          className="flex flex-col gap-sm"
        >
          <div className="flex items-baseline justify-between gap-sm">
            <h2 id="recent-title" className="text-section">
              Recent runs
            </h2>
            {runs.length > 0 && (
              <p className="text-small text-ink-subtle">On this device</p>
            )}
          </div>
          {runs.length === 0 ? (
            <p className="rounded-lg border border-dashed border-hairline-strong px-md py-sm text-body text-ink-muted">
              No runs yet. Search for a buyer above to start one.
            </p>
          ) : (
            <ul className="flex flex-col overflow-hidden rounded-lg border border-hairline bg-surface-1">
              {runs.map((run) => (
                <RecentRunRow key={run.runId} run={run} />
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="slack-title" className="flex flex-col gap-sm">
          <div className="flex items-baseline justify-between gap-sm">
            <h2 id="slack-title" className="text-section">
              Still in Slack
            </h2>
            <p className="text-small text-ink-subtle">Coming to the web</p>
          </div>
          <ul className="flex flex-col overflow-hidden rounded-lg border border-hairline bg-surface-1">
            {slackTools.map((tool) => (
              <li
                key={tool.id}
                className="flex flex-col gap-[2px] border-b border-hairline px-md py-[10px] last:border-b-0"
              >
                <span className="flex items-baseline justify-between gap-sm">
                  <span className="text-body font-medium text-ink">
                    {tool.name}
                  </span>
                  <code translate="no" className="text-small text-ink-subtle">
                    {tool.slackCommand}
                  </code>
                </span>
                <span className="text-small text-ink-subtle">
                  {tool.description}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}

// Each remembered run with its live state, so home shows what still needs review.
function RecentRunRow({ run }: { run: RecentRun }): React.JSX.Element {
  const query = useGetMatchRun(
    { path: { run_id: run.runId } },
    { query: { retry: false } },
  );
  const detail = query.data;
  const pending =
    detail?.candidates.filter((c) => c.status === "PENDING_REVIEW").length ?? 0;
  let state: React.ReactNode = null;
  if (query.isError) {
    state = <span className="text-small text-ink-subtle">Unavailable</span>;
  } else if (detail?.state === "completed") {
    state =
      pending > 0 ? (
        <span className="text-small text-ink">{pending} to review</span>
      ) : (
        <StatusBadge status="completed" />
      );
  } else if (detail) {
    state = <StatusBadge status={detail.state} />;
  }

  return (
    <li className="border-b border-hairline last:border-b-0">
      <Link
        to="/runs/$runId"
        params={{ runId: run.runId }}
        className="group grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-md px-md py-[10px] transition-colors hover:bg-surface-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]"
      >
        <span className="flex min-w-0 flex-col gap-[2px]">
          <span className="truncate text-body font-medium text-ink">
            {run.buyerName}
          </span>
          <span className="truncate text-small text-ink-subtle">
            <span className="sm:hidden">{relativeTime(run.startedAt)} · </span>
            {run.advisorContext ?? "No note"}
          </span>
        </span>
        <span className="flex justify-end sm:w-[104px]">{state}</span>
        <span className="hidden w-[124px] items-center justify-end gap-xs text-small text-ink-subtle sm:flex">
          {relativeTime(run.startedAt)}
          <ArrowRight
            aria-hidden
            className="size-4 -translate-x-1 opacity-0 transition-[opacity,transform] group-hover:translate-x-0 group-hover:opacity-100"
          />
        </span>
      </Link>
    </li>
  );
}
