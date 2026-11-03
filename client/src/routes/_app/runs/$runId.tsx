import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle } from "lucide-react";

import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DiscoveryStep,
  ExportStep,
  MatchingStep,
  ShortlistStep,
} from "@/features/find-match/RunSteps";
import { StepPanel } from "@/features/find-match/StepPanel";
import { StepsBar } from "@/features/find-match/StepsBar";
import { runSteps } from "@/features/find-match/steps";
import { useGetMatchRun } from "@/gen/hooks/useGetMatchRun";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";
import { ApiRequestError } from "@/lib/api-client";
import { relativeTime } from "@/lib/format";
import { findRecentRun } from "@/lib/recent-runs";

export const Route = createFileRoute("/_app/runs/$runId")({
  component: RunPage,
});

const POLL_MS = 2000;

function isBusy(run: RunDetailResponse | undefined): boolean {
  return run?.state === "running" || run?.discovery.status === "running";
}

function RunPage(): React.JSX.Element {
  const { runId } = Route.useParams();
  const recent = findRecentRun(runId);
  const query = useGetMatchRun(
    { path: { run_id: runId } },
    {
      query: {
        refetchInterval: (q) => (isBusy(q.state.data) ? POLL_MS : false),
      },
    },
  );
  const run = query.data;
  const buyerName = run?.buyer_org_name ?? recent?.buyerName ?? "Run";

  return (
    <>
      <TopBar
        crumbs={[
          { label: "Tools", to: "/" },
          { label: "Find match", to: "/find-match" },
          { label: buyerName },
        ]}
        trailing={run ? <StatusBadge status={run.state} /> : undefined}
      />
      {run ? (
        <StepsBar steps={runSteps(run)} />
      ) : (
        <div className="h-[49px] border-b border-hairline" />
      )}
      <main className="mx-auto flex w-full max-w-[760px] flex-col gap-lg px-md py-xl md:px-xl">
        <div className="flex flex-col gap-xxs">
          <h1 className="text-headline">{buyerName}</h1>
          <p className="text-body-sm text-ink-subtle">
            {run ? `Started ${relativeTime(run.started_at)}` : "Find-match run"}
            {" · "}
            <span className="font-mono text-mono">{runId.slice(0, 8)}</span>
          </p>
        </div>

        {query.isPending && (
          <div
            aria-busy="true"
            aria-label="Loading run"
            className="flex flex-col gap-sm"
          >
            {[0, 1, 2, 3].map((row) => (
              <Skeleton key={row} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        )}

        {query.isError && (
          <RunError error={query.error} onRetry={() => void query.refetch()} />
        )}

        {run && (
          <ol className="flex flex-col gap-sm">
            <StepPanel id="buyer" state="done" summary={run.buyer_org_name} />
            <StepPanel
              id="check"
              state="done"
              summary={
                recent?.advisorContext
                  ? `Note: ${recent.advisorContext}`
                  : "Checked before the run"
              }
            >
              {recent?.advisorContext ? (
                <p className="text-body-sm whitespace-pre-wrap text-ink-muted">
                  {recent.advisorContext}
                </p>
              ) : undefined}
            </StepPanel>
            <RunStepList run={run} />
          </ol>
        )}
      </main>
    </>
  );
}

function RunStepList({ run }: { run: RunDetailResponse }): React.JSX.Element {
  const steps = runSteps(run);
  return (
    <>
      <MatchingStep run={run} state={steps.match} />
      <ShortlistStep run={run} state={steps.shortlist} />
      <DiscoveryStep run={run} state={steps.discovery} />
      <ExportStep run={run} state={steps.export} />
    </>
  );
}

function RunError({
  error,
  onRetry,
}: {
  error: Error;
  onRetry: () => void;
}): React.JSX.Element {
  const notFound = error instanceof ApiRequestError && error.status === 404;
  return (
    <Alert tone={notFound ? "warning" : "danger"}>
      <AlertTriangle aria-hidden />
      <AlertTitle>
        {notFound ? "This run doesn't exist" : "Couldn't load this run"}
      </AlertTitle>
      <AlertDescription>
        <p>
          {notFound ? "It may belong to another environment." : error.message}
        </p>
        <div className="mt-xs flex gap-sm">
          {notFound ? (
            <Button asChild size="sm" variant="secondary">
              <Link to="/find-match">Start a new run</Link>
            </Button>
          ) : (
            <Button size="sm" variant="secondary" onClick={onRetry}>
              Retry
            </Button>
          )}
        </div>
      </AlertDescription>
    </Alert>
  );
}
