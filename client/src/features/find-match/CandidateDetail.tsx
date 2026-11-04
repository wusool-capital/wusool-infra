import { AlertTriangle, ArrowUpRight, Check, X } from "lucide-react";
import { useState } from "react";

import { candidateStatus } from "@/components/status";
import { StatusBadge } from "@/components/StatusBadge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { CandidateRead } from "@/gen/types/CandidateRead";
import type { ExistingDealRead } from "@/gen/types/ExistingDealRead";
import type { SellerProfileRead } from "@/gen/types/SellerProfileRead";
import { money, score } from "@/lib/format";

import { ResearchBlock } from "./ResearchBlock";
import { ScoreBar } from "./ScoreBar";
import { existingDeals, useDecision } from "./useDecision";

function Reasoning({
  candidate,
}: {
  candidate: CandidateRead;
}): React.JSX.Element | null {
  const sections = [
    ["Why it beat the others", candidate.why_chosen_over_alternatives],
    ["Recommended pitch", candidate.recommended_pitch],
    ["Risks and gaps", candidate.risks_and_gaps],
  ].filter(
    (entry): entry is [string, string] =>
      typeof entry[1] === "string" && entry[1].length > 0,
  );
  if (sections.length === 0) return null;
  return (
    <dl className="flex flex-col gap-md">
      {sections.map(([label, text]) => (
        <div key={label} className="flex flex-col gap-xxs">
          <dt className="text-small text-ink-subtle">{label}</dt>
          <dd className="text-body text-ink-muted">{text}</dd>
        </div>
      ))}
    </dl>
  );
}

// Slack's per-criterion line from View Full Analysis: type, result and what backs it.
function Criteria({
  candidate,
}: {
  candidate: CandidateRead;
}): React.JSX.Element | null {
  if (candidate.criteria.length === 0) return null;
  return (
    <section aria-label="Criteria" className="flex flex-col gap-xxs">
      <h4 className="text-small text-ink-subtle">Criteria</h4>
      <ul className="flex flex-col rounded-md border border-hairline">
        {candidate.criteria.map((c) => (
          <li
            key={`${c.criterion}-${c.criterion_type}`}
            className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-sm border-b border-hairline px-sm py-xs last:border-b-0"
          >
            <span className="text-body text-ink">
              {c.criterion.replaceAll("_", " ")}{" "}
              <span className="text-small text-ink-subtle">
                {c.criterion_type} · {c.data_backing.replaceAll("_", " ")}
              </span>
            </span>
            <span
              className={
                c.result === "Pass"
                  ? "text-small text-success"
                  : c.result === "Fail"
                    ? "text-small text-danger"
                    : "text-small text-ink-subtle"
              }
            >
              {c.result}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function websiteUrl(website: string): string {
  return /^https?:\/\//.test(website) ? website : `https://${website}`;
}

// What discovery wrote for a found seller: Google Maps plus basic enrichment, unverified by research.
function Profile({
  profile,
}: {
  profile: SellerProfileRead;
}): React.JSX.Element {
  const rows: [string, React.ReactNode][] = [];
  if (profile.hq_country) rows.push(["Country", profile.hq_country]);
  if (profile.sector_focus.length > 0)
    rows.push(["Sector", profile.sector_focus.join(", ")]);
  if (profile.website)
    rows.push([
      "Website",
      <a
        key="website"
        href={websiteUrl(profile.website)}
        target="_blank"
        rel="noreferrer noopener"
        className="text-ink underline decoration-hairline-tertiary underline-offset-4 hover:decoration-ink"
      >
        {profile.website}
      </a>,
    ]);
  if (profile.employee_range) rows.push(["Employees", profile.employee_range]);
  if (profile.founded_year !== null)
    rows.push(["Founded", String(profile.founded_year)]);
  if (profile.location_count !== null)
    rows.push(["Locations", String(profile.location_count)]);
  if (profile.est_revenue)
    rows.push(["Revenue (est.)", money(profile.est_revenue.amount)]);
  if (profile.est_ebitda)
    rows.push(["EBITDA (est.)", money(profile.est_ebitda.amount)]);
  return (
    <section aria-label="Company profile" className="flex flex-col gap-xs">
      <h4 className="text-small text-ink-subtle">
        What discovery found · Google Maps and basic enrichment
      </h4>
      {profile.description && (
        <p className="text-body text-ink-muted">{profile.description}</p>
      )}
      {rows.length > 0 ? (
        <dl className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-x-sm gap-y-xxs">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-body text-ink-subtle">{label}</dt>
              <dd className="text-body text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        !profile.description && (
          <p className="text-body text-ink-subtle">
            Enrichment found nothing beyond the name.
          </p>
        )
      )}
    </section>
  );
}

// Like Slack, at most three deals get a promote button.
const MAX_PROMOTABLE_DEALS = 3;

function DealChoice({
  deals,
  busy,
  onPromote,
  onCreate,
  onCancel,
}: {
  deals: ExistingDealRead[];
  busy: boolean;
  onPromote: (deal: ExistingDealRead) => void;
  onCreate: () => void;
  onCancel: () => void;
}): React.JSX.Element {
  return (
    <Alert tone="warning">
      <AlertTriangle aria-hidden />
      <AlertTitle>
        Attio already has a deal for this buyer and seller
      </AlertTitle>
      <AlertDescription>
        <p>
          Promote an existing deal to Qualified, or create a new one. Only an
          Inbound deal moves.
        </p>
        <ul className="mt-xs flex flex-col">
          {deals.slice(0, MAX_PROMOTABLE_DEALS).map((deal) => (
            <li
              key={deal.attio_id}
              className="flex flex-wrap items-center justify-between gap-sm border-t border-hairline py-xs"
            >
              <span className="flex flex-col">
                {deal.web_url ? (
                  <a
                    href={deal.web_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-[2px] text-ink underline decoration-hairline-tertiary underline-offset-4 hover:decoration-ink"
                  >
                    {deal.name}
                    <ArrowUpRight aria-hidden className="size-3.5" />
                    <span className="sr-only">(open in Attio)</span>
                  </a>
                ) : (
                  <span className="text-ink">{deal.name}</span>
                )}
                <span className="text-small text-ink-subtle">
                  {deal.stage ?? "No stage"}
                </span>
              </span>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  onPromote(deal);
                }}
              >
                Use this deal
              </Button>
            </li>
          ))}
        </ul>
        <div className="mt-xs flex flex-wrap gap-xs">
          <Button
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={onCreate}
          >
            Create a new deal
          </Button>
          <Button
            size="sm"
            variant="tertiary"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  );
}

// The selected candidate in full: its score, its case, and the decision.
export function CandidateDetail({
  runId,
  candidate,
  threshold,
  onDeciding,
  onDecided,
}: {
  runId: string;
  candidate: CandidateRead;
  threshold: number;
  onDeciding?: (candidateId: string) => void;
  onDecided?: (candidateId: string) => void;
}): React.JSX.Element {
  const decision = useDecision(runId, candidate.id);
  const [choosing, setChoosing] = useState(false);
  const deals = choosing ? existingDeals(decision.error) : null;
  const pending = candidate.status === "PENDING_REVIEW";
  const discovered = candidate.origin === "discovery";
  const failure =
    decision.isError && deals === null ? decision.error.message : null;
  const decided = (): void => onDecided?.(candidate.id);

  const approve = (resolution?: {
    resolution: "promote_existing" | "create_new";
    existing_deal_id?: string;
  }): void => {
    setChoosing(false);
    onDeciding?.(candidate.id);
    decision.mutate(
      resolution ? { kind: "approve", resolution } : { kind: "approve" },
      {
        onSuccess: decided,
        onError: (error) => {
          if (existingDeals(error) !== null) setChoosing(true);
        },
      },
    );
  };

  return (
    <article
      aria-labelledby={`candidate-${candidate.id}`}
      className="flex animate-rise flex-col gap-lg"
    >
      <header className="flex flex-col gap-xs">
        <div className="flex items-start justify-between gap-sm">
          <h3
            id={`candidate-${candidate.id}`}
            className="text-figure font-medium text-balance"
          >
            {candidate.seller_org_name}
          </h3>
          <StatusBadge status={candidateStatus(candidate.status)} />
        </div>
        {discovered ? (
          <p className="text-body text-ink-subtle">
            Found via Google Maps · not scored
            {candidate.source_url && (
              <>
                {" · "}
                <a
                  href={candidate.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex items-center gap-[2px] text-ink underline decoration-hairline-tertiary underline-offset-4 hover:decoration-ink"
                >
                  View on Maps <ArrowUpRight aria-hidden className="size-3.5" />
                </a>
              </>
            )}
          </p>
        ) : (
          <p className="text-body text-ink-subtle">
            Rank {candidate.rank} · Data confidence{" "}
            <span className="text-ink-muted">
              {score(candidate.data_confidence)}
            </span>
            /100
          </p>
        )}
      </header>

      {!discovered && candidate.match_score != null && (
        <ScoreBar value={candidate.match_score} threshold={threshold} />
      )}

      {candidate.why_it_matches && (
        <p className="text-lead text-ink">{candidate.why_it_matches}</p>
      )}
      {!discovered && <Criteria candidate={candidate} />}
      {!discovered && <Reasoning candidate={candidate} />}
      {discovered && pending && (
        <p className="text-body text-ink-subtle">
          Unverified and unscored; approve to open a Qualified deal.
        </p>
      )}
      {discovered && candidate.profile && (
        <Profile profile={candidate.profile} />
      )}

      {discovered && candidate.status === "APPROVED" && (
        <ResearchBlock
          // A fresh mount once research lands, so its ticked fields start from the results.
          key={candidate.research?.status ?? "none"}
          runId={runId}
          candidateId={candidate.id}
          orgName={candidate.seller_org_name}
          research={candidate.research ?? null}
        />
      )}

      {deals !== null && (
        <DealChoice
          deals={deals}
          busy={decision.isPending}
          onPromote={(deal) => {
            approve({
              resolution: "promote_existing",
              existing_deal_id: deal.attio_id,
            });
          }}
          onCreate={() => {
            approve({ resolution: "create_new" });
          }}
          onCancel={() => {
            setChoosing(false);
            decision.reset();
          }}
        />
      )}
      {failure && (
        <Alert tone="danger">
          <AlertTriangle aria-hidden />
          <AlertTitle>{failure}</AlertTitle>
        </Alert>
      )}

      {pending && deals === null && (
        <div className="flex flex-wrap gap-xs border-t border-hairline pt-md lg:sticky lg:bottom-0 lg:-mx-lg lg:bg-surface-1 lg:px-lg lg:pb-lg">
          <Button
            size="lg"
            disabled={decision.isPending}
            onClick={() => {
              approve();
            }}
          >
            <Check aria-hidden />
            Approve
          </Button>
          <Button
            size="lg"
            variant="danger"
            disabled={decision.isPending}
            onClick={() => {
              onDeciding?.(candidate.id);
              decision.mutate({ kind: "reject" }, { onSuccess: decided });
            }}
          >
            <X aria-hidden />
            Reject
          </Button>
        </div>
      )}
      {candidate.status === "APPROVED" && decision.isSuccess && (
        <p role="status" className="text-body text-ink-muted">
          Match with {candidate.seller_org_name} approved.
        </p>
      )}
      {!pending && (
        <p className="border-t border-hairline pt-md text-body text-ink-subtle lg:sticky lg:bottom-0 lg:-mx-lg lg:bg-surface-1 lg:px-lg lg:pb-lg">
          {candidate.deal_attio_id ? (
            <>
              Qualified deal in Attio{" "}
              <code translate="no" className="text-ink-muted">
                {candidate.deal_attio_id}
              </code>
            </>
          ) : candidate.status === "APPROVED" ? (
            "Approved."
          ) : (
            "Rejected. Nothing was written to Attio."
          )}
        </p>
      )}
    </article>
  );
}
