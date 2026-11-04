import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { AlertTriangle, Download, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getMatchRunQueryKey } from "@/gen/hooks/useGetMatchRun";
import { useStartDiscovery } from "@/gen/hooks/useStartDiscovery";
import type { CandidateRead } from "@/gen/types/CandidateRead";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useExportFields } from "@/lib/export-fields";
import { score } from "@/lib/format";

import { CandidateDetail } from "./CandidateDetail";
import { CandidateList, type CandidateGroup } from "./CandidateList";
import { downloadRunCsv } from "./download";
import { ThresholdStrip } from "./RunFunnel";

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

function SectionTitle({
  id,
  children,
  aside,
}: {
  id: string;
  children: React.ReactNode;
  aside?: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="flex items-baseline justify-between gap-sm">
      <h2 id={id} className="text-section">
        {children}
      </h2>
      {aside && <p className="text-small text-ink-subtle">{aside}</p>}
    </div>
  );
}

function ListSkeleton(): React.JSX.Element {
  return (
    <div
      aria-hidden
      className="flex flex-col rounded-lg border border-hairline bg-surface-1"
    >
      {[0, 1, 2, 3, 4].map((row) => (
        <div
          key={row}
          className="grid min-h-14 grid-cols-[24px_1fr_56px] items-center gap-sm border-b border-hairline px-md last:border-b-0"
        >
          <Skeleton className="h-3 w-3" />
          <span className="flex flex-col gap-[6px]">
            <Skeleton className="h-[14px] w-48 max-w-full" />
            <Skeleton className="h-[10px] w-24" />
          </span>
          <Skeleton className="h-[14px] w-8 justify-self-end" />
        </div>
      ))}
    </div>
  );
}

function StartAgain({ buyerName }: { buyerName: string }): React.JSX.Element {
  return (
    <Button asChild variant="secondary" className="self-start">
      <Link to="/find-match" search={{ q: buyerName }}>
        Start a new run
      </Link>
    </Button>
  );
}

// What the review area shows before there is a shortlist: progress, or why there won't be one.
export function RunProgress({
  run,
}: {
  run: RunDetailResponse;
}): React.JSX.Element | null {
  const now = useNow(run.state === "running");
  if (run.state === "running") {
    return (
      <div className="grid gap-lg lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <ListSkeleton />
        <div className="flex flex-col gap-xs" aria-live="polite">
          <p className="text-figure">{elapsed(run.started_at, now)}</p>
          <p className="text-lead text-ink-muted">
            Reading the mandate, filtering the CRM's sellers and writing the
            reasoning. This usually takes under a minute.
          </p>
        </div>
      </div>
    );
  }
  if (run.state === "stale" || run.state === "failed") {
    const stale = run.state === "stale";
    return (
      <div className="flex max-w-[680px] flex-col gap-md">
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
      </div>
    );
  }
  return null;
}

function firstPending(candidates: CandidateRead[]): string | null {
  return (
    candidates.find((c) => c.status === "PENDING_REVIEW")?.id ??
    candidates[0]?.id ??
    null
  );
}

// Shortlist and discovered sellers in one ranked list, with the selected one in full beside it.
export function Review({
  run,
  notes,
}: {
  run: RunDetailResponse;
  notes?: React.ReactNode;
}): React.JSX.Element {
  const wide = useMediaQuery("(min-width: 1024px)");
  const crm = run.candidates.filter((c) => c.origin === "crm");
  const found = run.candidates.filter((c) => c.origin === "discovery");
  const all = [...crm, ...found];
  const [chosen, setChosen] = useState<string | null>(null);
  const selectedId =
    chosen !== null && all.some((c) => c.id === chosen)
      ? chosen
      : firstPending(all);
  const selected = all.find((c) => c.id === selectedId);
  const best = Math.max(0, ...crm.map((c) => c.match_score ?? 0));

  // After a decision, move on to the next candidate still waiting.
  const advance = (decidedId: string): void => {
    const from = all.findIndex((c) => c.id === decidedId);
    const rest = [...all.slice(from + 1), ...all.slice(0, from)];
    const next = rest.find((c) => c.status === "PENDING_REVIEW");
    if (next) setChosen(next.id);
  };

  const groups: CandidateGroup[] = [
    {
      id: "crm",
      title: `From the CRM · ${String(crm.length)}`,
      candidates: crm,
    },
    ...(found.length > 0
      ? [
          {
            id: "found",
            title: `Found outside the CRM · ${String(found.length)}`,
            candidates: found,
          },
        ]
      : []),
  ];
  const detail = selected ? (
    <CandidateDetail
      key={selected.id}
      runId={run.run_id}
      candidate={selected}
      threshold={run.discovery_threshold}
      // Pin it: the optimistic decision would otherwise move "first pending" away and lose a failure.
      onDeciding={setChosen}
      onDecided={advance}
    />
  ) : null;

  return (
    // On desktop the review fills the window; list and detail scroll on their own.
    <div className="grid items-start gap-lg lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:items-stretch">
      <div className="flex min-w-0 flex-col gap-xl lg:min-h-0 lg:overflow-y-auto lg:pb-lg">
        <section
          aria-labelledby="shortlist-title"
          className="flex flex-col gap-sm"
        >
          <SectionTitle
            id="shortlist-title"
            aside={
              all.length > 0 ? (
                <span className="hidden lg:inline">↑ ↓ to move</span>
              ) : undefined
            }
          >
            Shortlist
          </SectionTitle>
          {run.low_match_quality && crm.length > 0 && (
            <Alert tone="warning">
              <AlertTriangle aria-hidden />
              <AlertTitle>Low match quality</AlertTitle>
              <AlertDescription>
                The best score is {score(best)}, below the{" "}
                {score(run.discovery_threshold)} threshold, so discovery
                searches outside the CRM.
              </AlertDescription>
            </Alert>
          )}
          {crm.length > 0 && crm.length < 3 && (
            <p className="text-body text-ink-subtle">
              Only {crm.length} qualifying candidate
              {crm.length === 1 ? "" : "s"} available — fewer than 3.
            </p>
          )}
          {all.length === 0 ? (
            <p className="rounded-lg border border-dashed border-hairline-strong px-md py-sm text-body text-ink-muted">
              No seller in the CRM passed the filters and the sector check for
              this buyer.
            </p>
          ) : (
            <CandidateList
              groups={groups}
              threshold={run.discovery_threshold}
              selectedId={selectedId}
              onSelect={setChosen}
              inlineDetail={wide ? undefined : detail}
            />
          )}
        </section>
        <DiscoverySection run={run} />
        <MandateSection run={run} />
        {notes}
      </div>

      {wide && (
        <aside
          aria-label="Selected candidate"
          className="flex min-h-0 flex-col gap-md lg:pb-lg"
        >
          {crm.length > 0 && (
            <ThresholdStrip run={run} selectedId={selectedId} />
          )}
          {detail && (
            <div className="min-h-0 scroll-pb-24 overflow-y-auto overscroll-contain rounded-lg border border-hairline bg-surface-1 px-lg pt-lg">
              {detail}
            </div>
          )}
        </aside>
      )}
    </div>
  );
}

// Slack's "Buyer & Mandate" from View Full Analysis: what the run matched against.
export function MandateSection({
  run,
}: {
  run: RunDetailResponse;
}): React.JSX.Element | null {
  const { mandate } = run;
  if (!mandate) return null;
  return (
    <section aria-labelledby="mandate-title" className="flex flex-col gap-sm">
      <SectionTitle id="mandate-title">Buyer and mandate</SectionTitle>
      <dl className="flex flex-col rounded-lg border border-hairline bg-surface-1">
        {(
          [
            ["Strategic thesis", mandate.strategic_thesis ?? "Unknown"],
            ["Ideal target", mandate.ideal_target ?? "Unknown"],
          ] as const
        ).map(([label, text]) => (
          <div
            key={label}
            className="grid gap-xxs border-b border-hairline px-md py-sm md:grid-cols-[minmax(0,2fr)_minmax(0,5fr)] md:gap-md"
          >
            <dt className="text-body text-ink-subtle">{label}</dt>
            <dd className="text-body text-ink">{text}</dd>
          </div>
        ))}
        <div className="grid gap-xxs px-md py-sm md:grid-cols-[minmax(0,2fr)_minmax(0,5fr)] md:gap-md">
          <dt className="text-body text-ink-subtle">Hard requirements</dt>
          <dd>
            {mandate.hard_requirements.length === 0 ? (
              <p className="text-body text-ink">None extracted.</p>
            ) : (
              <ul className="flex flex-col gap-xxs">
                {mandate.hard_requirements.map((r) => (
                  <li
                    key={`${r.criterion}-${r.value ?? ""}`}
                    className="text-body text-ink"
                  >
                    {r.criterion.replaceAll("_", " ")}: {r.value ?? "Unknown"}{" "}
                    <span className="text-small text-ink-subtle">
                      {r.source.replaceAll("_", " ")}
                      {r.human_confirmed ? " · confirmed" : " · not confirmed"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </dd>
        </div>
      </dl>
    </section>
  );
}

// Search outside the CRM: offered on every finished run, then its outcome.
export function DiscoverySection({
  run,
}: {
  run: RunDetailResponse;
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
  const { discovery } = run;
  const found = run.candidates.filter((c) => c.origin === "discovery");

  const findMore = (
    <>
      {startDiscovery.isError && (
        <p role="alert" className="text-body text-danger">
          {startDiscovery.error.message}
        </p>
      )}
      <Button
        variant="secondary"
        disabled={startDiscovery.isPending || run.state !== "completed"}
        onClick={() => {
          startDiscovery.mutate({ path: { run_id: run.run_id } });
        }}
      >
        <Search aria-hidden />
        {discovery.status === "not_needed"
          ? "Find more sellers anyway"
          : "Find more sellers"}
      </Button>
    </>
  );

  let body: React.ReactNode;
  if (discovery.status === "not_needed") {
    // As in Slack, the advisor can still search when the CRM shortlist looks good.
    body = (
      <div className="flex flex-col items-start gap-sm">
        <p className="text-body text-ink-muted">
          Not needed: the shortlist cleared the {score(run.discovery_threshold)}{" "}
          line. You can still search Google Maps for sellers the CRM doesn't
          have yet.
        </p>
        {findMore}
      </div>
    );
  } else if (discovery.status === "running") {
    body = (
      <p
        className="flex items-center gap-xs text-body text-ink-muted"
        aria-live="polite"
      >
        <span
          aria-hidden
          className="size-[6px] animate-pulse rounded-full bg-primary"
        />
        Searching Google Maps and checking each lead against the CRM. New
        sellers join the shortlist for review.
      </p>
    );
  } else if (discovery.status === "available") {
    body = (
      <div className="flex flex-col items-start gap-sm rounded-lg border border-hairline bg-surface-1 p-md">
        <p className="text-body text-ink-muted">
          Every score is under the {score(run.discovery_threshold)} line. Search
          Google Maps for sellers in this buyer's sector and geography;
          genuinely new ones are added to the CRM for review.
        </p>
        {findMore}
      </div>
    );
  } else if (discovery.status !== "done") {
    body = (
      <Alert tone={discovery.status === "failed" ? "danger" : "warning"}>
        <AlertTriangle aria-hidden />
        <AlertTitle>{discovery.message ?? "Discovery couldn't run"}</AlertTitle>
      </Alert>
    );
  } else {
    body = (
      <div className="flex flex-col gap-xxs text-body text-ink-muted">
        <p className={found.length > 0 ? "text-ink" : undefined}>
          {discovery.message ??
            (found.length > 0
              ? `${String(found.length)} new sellers added to the shortlist.`
              : "No new potential sellers found.")}
        </p>
        {discovery.notes.map((note) => (
          <p key={note}>{note}</p>
        ))}
      </div>
    );
  }

  return (
    <section aria-labelledby="discovery-title" className="flex flex-col gap-sm">
      <SectionTitle id="discovery-title">Outside the CRM</SectionTitle>
      {body}
    </section>
  );
}

export function ExportButton({
  run,
}: {
  run: RunDetailResponse;
}): React.JSX.Element {
  const [exportError, setExportError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fields = useExportFields();
  const unreviewed = run.candidates.filter(
    (c) => c.research?.status === "done" && !c.research.reviewed,
  ).length;
  return (
    // Anything left to review sits under the button.
    <div className="flex flex-col items-end gap-xxs">
      <Button
        variant="secondary"
        disabled={busy || run.state !== "completed"}
        onClick={() => {
          setBusy(true);
          setExportError(null);
          downloadRunCsv(run.run_id, fields)
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
      {unreviewed > 0 && (
        <span className="text-small text-ink-subtle">
          {unreviewed} seller{unreviewed === 1 ? "'s" : "s'"} research not
          reviewed
        </span>
      )}
      {exportError && (
        <p role="alert" className="text-small text-danger">
          {exportError}
        </p>
      )}
    </div>
  );
}
