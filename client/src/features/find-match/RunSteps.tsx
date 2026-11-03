import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { AlertTriangle, Download } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getMatchRunQueryKey } from "@/gen/hooks/useGetMatchRun";
import { useStartDiscovery } from "@/gen/hooks/useStartDiscovery";
import type { CandidateRead } from "@/gen/types/CandidateRead";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";
import { score } from "@/lib/format";

import { CandidateCard } from "./CandidateCard";
import { downloadRunCsv } from "./download";
import { StepPanel } from "./StepPanel";
import type { StepStates } from "./steps";

function elapsed(startedAt: string, now: number): string {
  const seconds = Math.max(
    0,
    Math.round((now - new Date(startedAt).getTime()) / 1000),
  );
  return seconds < 60
    ? `${String(seconds)}s`
    : `${String(Math.floor(seconds / 60))}m ${String(seconds % 60)}s`;
}

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => {
      clearInterval(timer);
    };
  }, [active]);
  return now;
}

function CandidateSkeleton(): React.JSX.Element {
  return (
    <div
      aria-hidden
      className="flex flex-col gap-md rounded-lg border border-hairline bg-surface-1 p-md"
    >
      <Skeleton className="h-5 w-56" />
      <Skeleton className="h-[6px] w-full" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}

function reviewCount(candidates: CandidateRead[]): string {
  const approved = candidates.filter((c) => c.status === "APPROVED").length;
  const rejected = candidates.filter((c) => c.status === "REJECTED").length;
  const pending = candidates.length - approved - rejected;
  return pending > 0
    ? `${String(pending)} of ${String(candidates.length)} to review`
    : `${String(approved)} approved · ${String(rejected)} rejected`;
}

function StartAgain({ buyerName }: { buyerName: string }): React.JSX.Element {
  return (
    <Button asChild className="self-start">
      <Link to="/find-match" search={{ q: buyerName }}>
        Start a new run
      </Link>
    </Button>
  );
}

export function MatchingStep({
  run,
  state,
}: {
  run: RunDetailResponse;
  state: StepStates["match"];
}): React.JSX.Element {
  const now = useNow(run.state === "running");
  if (run.state === "running") {
    return (
      <StepPanel
        id="match"
        state={state}
        summary={`Running for ${elapsed(run.started_at, now)}`}
      >
        <p className="text-body-sm text-ink-muted" aria-live="polite">
          Reading the mandate, filtering the CRM's sellers and writing the
          reasoning. This usually takes under a minute.
        </p>
        <CandidateSkeleton />
      </StepPanel>
    );
  }
  if (run.state === "stale" || run.state === "failed") {
    const stale = run.state === "stale";
    return (
      <StepPanel
        id="match"
        state={state}
        summary={stale ? "Stopped responding" : "Failed"}
      >
        <Alert tone={stale ? "warning" : "danger"}>
          <AlertTriangle aria-hidden />
          <AlertTitle>
            {stale ? "This run never finished" : "Matching failed"}
          </AlertTitle>
          <AlertDescription>
            {stale
              ? "The server restarted while it ran, so no results were saved."
              : (run.error ??
                "Matching failed before results could be generated.")}{" "}
            Nothing was written to the CRM.
          </AlertDescription>
        </Alert>
        <StartAgain buyerName={run.buyer_org_name} />
      </StepPanel>
    );
  }
  const shortlisted = run.candidates.filter((c) => c.origin === "crm").length;
  return (
    <StepPanel
      id="match"
      state={state}
      summary={`${score(run.candidates_considered ?? null)} sellers considered · ${score(run.candidates_filtered ?? null)} passed filters · ${String(shortlisted)} shortlisted`}
    >
      {run.notes.length > 0 && (
        <ul className="flex flex-col gap-xxs text-body-sm text-ink-muted">
          {run.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </StepPanel>
  );
}

export function ShortlistStep({
  run,
  state,
}: {
  run: RunDetailResponse;
  state: StepStates["shortlist"];
}): React.JSX.Element {
  if (run.state !== "completed") {
    return (
      <StepPanel
        id="shortlist"
        state="upcoming"
        summary="Appears when matching finishes"
      />
    );
  }
  const candidates = run.candidates.filter((c) => c.origin === "crm");
  const best = Math.max(0, ...candidates.map((c) => c.match_score ?? 0));
  return (
    <StepPanel
      id="shortlist"
      state={state}
      summary={
        candidates.length === 0
          ? "No CRM seller qualified"
          : reviewCount(candidates)
      }
    >
      {run.low_match_quality && candidates.length > 0 && (
        <Alert tone="warning">
          <AlertTriangle aria-hidden />
          <AlertTitle>Low match quality</AlertTitle>
          <AlertDescription>
            The best score is {score(best)}, below the{" "}
            {score(run.discovery_threshold)} threshold, so discovery searches
            outside the CRM.
          </AlertDescription>
        </Alert>
      )}
      {candidates.length === 0 ? (
        <p className="text-body-sm text-ink-muted">
          No seller in the CRM passed the filters and the sector check for this
          buyer.
        </p>
      ) : (
        <div className="flex flex-col gap-sm">
          {candidates.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              runId={run.run_id}
              candidate={candidate}
              threshold={run.discovery_threshold}
            />
          ))}
        </div>
      )}
    </StepPanel>
  );
}

export function DiscoveryStep({
  run,
  state,
}: {
  run: RunDetailResponse;
  state: StepStates["discovery"];
}): React.JSX.Element {
  const queryClient = useQueryClient();
  const startDiscovery = useStartDiscovery({
    mutation: {
      onSuccess: () => {
        // The search starts after the response; show it as running so polling resumes.
        queryClient.setQueryData<RunDetailResponse>(
          getMatchRunQueryKey({ path: { run_id: run.run_id } }),
          (current) =>
            current
              ? {
                  ...current,
                  discovery: { ...current.discovery, status: "running" },
                }
              : current,
        );
      },
    },
  });
  if (run.state !== "completed") {
    return (
      <StepPanel
        id="discovery"
        state="upcoming"
        summary="Runs if every score is low"
      />
    );
  }
  const { discovery } = run;
  const found = run.candidates.filter((c) => c.origin === "discovery");

  if (discovery.status === "not_needed") {
    return (
      <StepPanel
        id="discovery"
        state={state}
        summary={`Not needed: the shortlist cleared the ${score(run.discovery_threshold)} threshold`}
      />
    );
  }
  if (discovery.status === "running") {
    return (
      <StepPanel
        id="discovery"
        state={state}
        summary="Searching Google Maps for new sellers"
      >
        <p className="text-body-sm text-ink-muted" aria-live="polite">
          Checking each lead against the CRM. New sellers are created and added
          below for review.
        </p>
        <CandidateSkeleton />
      </StepPanel>
    );
  }
  if (discovery.status === "available") {
    return (
      <StepPanel
        id="discovery"
        state={state}
        summary="Every score is low; search outside the CRM"
      >
        <p className="text-body-sm text-ink-muted">
          Searches Google Maps for sellers in this buyer's sector and geography
          and adds the genuinely new ones to the CRM for review.
        </p>
        {startDiscovery.isError && (
          <p role="alert" className="text-body-sm text-danger">
            {startDiscovery.error.message}
          </p>
        )}
        <Button
          className="self-start"
          disabled={startDiscovery.isPending}
          onClick={() => {
            startDiscovery.mutate({ path: { run_id: run.run_id } });
          }}
        >
          Find more sellers
        </Button>
      </StepPanel>
    );
  }
  if (discovery.status !== "done") {
    return (
      <StepPanel
        id="discovery"
        state={state}
        summary={discovery.message ?? "Discovery couldn't run"}
      >
        <Alert tone={discovery.status === "failed" ? "danger" : "warning"}>
          <AlertTriangle aria-hidden />
          <AlertTitle>
            {discovery.message ?? "Discovery couldn't run"}
          </AlertTitle>
        </Alert>
      </StepPanel>
    );
  }
  return (
    <StepPanel
      id="discovery"
      state={state}
      summary={
        found.length === 0
          ? (discovery.message ?? "No new sellers found")
          : reviewCount(found)
      }
    >
      {found.length > 0 && discovery.message && (
        <p className="text-body-sm text-ink">{discovery.message}</p>
      )}
      {discovery.notes.length > 0 && (
        <ul className="flex flex-col gap-xxs text-body-sm text-ink-muted">
          {discovery.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      {found.length === 0 ? (
        <p className="text-body-sm text-ink-muted">
          {discovery.message ?? "No new potential sellers found."}
        </p>
      ) : (
        <div className="flex flex-col gap-sm">
          {found.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              runId={run.run_id}
              candidate={candidate}
              threshold={run.discovery_threshold}
            />
          ))}
        </div>
      )}
    </StepPanel>
  );
}

export function ExportStep({
  run,
  state,
}: {
  run: RunDetailResponse;
  state: StepStates["export"];
}): React.JSX.Element {
  const [exportError, setExportError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (run.state !== "completed") {
    return (
      <StepPanel
        id="export"
        state="upcoming"
        summary="Download the shortlist as CSV"
      />
    );
  }
  return (
    <StepPanel
      id="export"
      state={state}
      summary={
        state === "upcoming"
          ? "Available now; decisions so far are included"
          : "Shortlist with every decision"
      }
    >
      <div className="flex flex-wrap items-center gap-sm">
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            setExportError(null);
            downloadRunCsv(run.run_id)
              .catch((error: unknown) => {
                setExportError(
                  error instanceof Error ? error.message : "Export failed",
                );
              })
              .finally(() => {
                setBusy(false);
              });
          }}
        >
          <Download aria-hidden />
          {busy ? "Preparing…" : "Download CSV"}
        </Button>
        {exportError && (
          <p role="alert" className="text-body-sm text-danger">
            {exportError}
          </p>
        )}
      </div>
    </StepPanel>
  );
}
