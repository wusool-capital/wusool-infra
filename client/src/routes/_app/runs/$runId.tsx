import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle } from "lucide-react";

import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RunFunnel } from "@/features/find-match/RunFunnel";
import {
  ExportButton,
  Review,
  RunProgress,
} from "@/features/find-match/RunReview";
import { StepsBar } from "@/features/find-match/StepsBar";
import { runSteps } from "@/features/find-match/steps";
import { useGetMatchRun } from "@/gen/hooks/useGetMatchRun";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";
import { ApiRequestError } from "@/lib/api-client";
import { relativeTime, score } from "@/lib/format";
import { findRecentRun } from "@/lib/recent-runs";

export const Route = createFileRoute("/_app/runs/$runId")({
  component: RunPage,
});

const POLL_MS = 2000;

function isBusy(run: RunDetailResponse | undefined): boolean {
  return (
    run?.state === "running" ||
    run?.discovery.status === "running" ||
    (run?.candidates.some((c) => c.research?.status === "running") ?? false)
  );
}

// The line under the title: the one fact the advisor needs first.
function finding(run: RunDetailResponse): string {
  if (run.state === "running")
    return "Matching now. The shortlist appears here.";
  if (run.state === "stale") return "This run stopped before it finished.";
  if (run.state === "failed") return "Matching failed; nothing was saved.";
  const crm = run.candidates.filter((c) => c.origin === "crm");
  if (crm.length === 0) return "No CRM seller qualified for this mandate.";
  const pending = run.candidates.filter(
    (c) => c.status === "PENDING_REVIEW",
  ).length;
  const best = Math.max(0, ...crm.map((c) => c.match_score ?? 0));
  const review =
    pending > 0
      ? `${String(pending)} of ${String(run.candidates.length)} left to review`
      : "Every candidate decided";
  return `${review} · best score ${score(best)}`;
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
    <main
      id="main"
      tabIndex={-1}
      className="mx-auto flex w-full max-w-[1360px] flex-col gap-lg px-md py-lg outline-none md:px-xl md:py-xl lg:h-full lg:min-h-[720px] lg:pb-0"
    >
      <PageHeader
        parent={{ label: "Find match", to: "/" }}
        title={buyerName}
        sub={
          run ? (
            finding(run)
          ) : (
            <span className="text-ink-subtle">Find-match run</span>
          )
        }
        actions={
          run ? (
            <>
              <StatusBadge status={run.state} />
              <ExportButton run={run} />
            </>
          ) : undefined
        }
      />

      {run ? (
        <StepsBar steps={runSteps(run)} />
      ) : (
        <div className="h-[37px] border-b border-hairline" />
      )}

      {query.isPending && (
        <div
          aria-busy="true"
          aria-label="Loading run"
          className="flex flex-col gap-lg"
        >
          <Skeleton className="h-[98px] w-full" />
          <Skeleton className="h-72 w-full lg:w-7/12" />
        </div>
      )}

      {query.isError && (
        <RunError error={query.error} onRetry={() => void query.refetch()} />
      )}

      {run && (
        <>
          <RunFunnel run={run} />
          {run.state === "completed" ? (
            <Review
              run={run}
              notes={
                <RunNotes run={run} note={recent?.advisorContext ?? null} />
              }
            />
          ) : (
            <RunProgress run={run} />
          )}
        </>
      )}
    </main>
  );
}

function RunNotes({
  run,
  note,
}: {
  run: RunDetailResponse;
  note: string | null;
}): React.JSX.Element {
  return (
    <section aria-labelledby="notes-title" className="flex flex-col gap-sm">
      <h2 id="notes-title" className="text-section">
        Run notes
      </h2>
      <dl className="flex flex-col rounded-lg border border-hairline bg-surface-1">
        <div className="grid gap-xxs px-md py-sm sm:grid-cols-[160px_1fr] sm:gap-md">
          <dt className="text-small text-ink-subtle sm:pt-[2px]">Your note</dt>
          <dd className="text-body whitespace-pre-wrap text-ink-muted">
            {note ?? "No note. The match used the buyer's CRM profile."}
          </dd>
        </div>
        <div className="grid gap-xxs border-t border-hairline px-md py-sm sm:grid-cols-[160px_1fr] sm:gap-md">
          <dt className="text-small text-ink-subtle sm:pt-[2px]">Started</dt>
          <dd className="text-body text-ink-muted">
            {relativeTime(run.started_at)} ·{" "}
            <span translate="no">{run.run_id.slice(0, 8)}</span>
          </dd>
        </div>
        {run.notes.length > 0 && (
          <div className="grid gap-xxs border-t border-hairline px-md py-sm sm:grid-cols-[160px_1fr] sm:gap-md">
            <dt className="text-small text-ink-subtle sm:pt-[2px]">
              From the engine
            </dt>
            <dd>
              <ul className="flex flex-col gap-xxs text-body text-ink-muted">
                {run.notes.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </dd>
          </div>
        )}
      </dl>
    </section>
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
    <Alert tone={notFound ? "warning" : "danger"} className="max-w-[680px]">
      <AlertTriangle aria-hidden />
      <AlertTitle>
        {notFound ? "This run doesn't exist" : "Couldn't load this run"}
      </AlertTitle>
      <AlertDescription>
        <p>
          {notFound ? "It may belong to another environment." : error.message}
        </p>
        <div className="mt-xs flex gap-xs">
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
