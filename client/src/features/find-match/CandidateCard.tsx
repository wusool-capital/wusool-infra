import { AlertTriangle, ExternalLink } from "lucide-react";
import { useState } from "react";

import { candidateStatus } from "@/components/status";
import { StatusBadge } from "@/components/StatusBadge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { CandidateRead } from "@/gen/types/CandidateRead";
import type { ExistingDealRead } from "@/gen/types/ExistingDealRead";
import { score } from "@/lib/format";

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
    <details className="group">
      <summary className="cursor-pointer text-body-sm text-primary-hover hover:underline">
        Full reasoning
      </summary>
      <dl className="mt-sm flex flex-col gap-sm">
        {sections.map(([label, text]) => (
          <div key={label} className="flex flex-col gap-xxs">
            <dt className="text-caption text-ink-subtle">{label}</dt>
            <dd className="text-body-sm text-ink-muted">{text}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

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
        <ul className="mt-xs flex flex-col gap-xs">
          {deals.map((deal) => (
            <li
              key={deal.attio_id}
              className="flex flex-wrap items-center gap-sm"
            >
              <span className="text-ink">{deal.name}</span>
              <span className="text-caption text-ink-subtle">
                {deal.stage ?? "No stage"}
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
        <div className="mt-xs flex flex-wrap gap-sm">
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

export function CandidateCard({
  runId,
  candidate,
  threshold,
}: {
  runId: string;
  candidate: CandidateRead;
  threshold: number;
}): React.JSX.Element {
  const decision = useDecision(runId, candidate.id);
  const [choosing, setChoosing] = useState(false);
  const deals = choosing ? existingDeals(decision.error) : null;
  const pending = candidate.status === "PENDING_REVIEW";
  const discovered = candidate.origin === "discovery";
  const failure =
    decision.isError && deals === null ? decision.error.message : null;

  const approve = (resolution?: {
    resolution: "promote_existing" | "create_new";
    existing_deal_id?: string;
  }): void => {
    setChoosing(false);
    decision.mutate(
      resolution ? { kind: "approve", resolution } : { kind: "approve" },
      {
        onError: (error) => {
          if (existingDeals(error) !== null) setChoosing(true);
        },
      },
    );
  };

  return (
    <article
      aria-labelledby={`candidate-${candidate.id}`}
      className="flex flex-col gap-md rounded-lg border border-hairline bg-surface-1 p-md"
    >
      <header className="flex flex-wrap items-start justify-between gap-sm">
        <div className="flex min-w-0 flex-col gap-xxs">
          <h3
            id={`candidate-${candidate.id}`}
            className="text-body font-medium text-ink"
          >
            {discovered ? null : (
              <span className="text-ink-subtle tabular-nums">
                {candidate.rank}.{" "}
              </span>
            )}
            {candidate.seller_org_name}
          </h3>
          {discovered ? (
            <p className="text-caption text-ink-subtle">
              Found via Google Maps · not scored
              {candidate.source_url && (
                <>
                  {" · "}
                  <a
                    href={candidate.source_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-[2px] text-primary-hover hover:underline"
                  >
                    Website <ExternalLink aria-hidden className="size-3" />
                  </a>
                </>
              )}
            </p>
          ) : (
            <p className="text-caption text-ink-subtle">
              Data confidence{" "}
              <span className="tabular-nums">
                {score(candidate.data_confidence)}
              </span>
              /100
            </p>
          )}
        </div>
        <StatusBadge status={candidateStatus(candidate.status)} />
      </header>

      {!discovered && candidate.match_score != null && (
        <ScoreBar value={candidate.match_score} threshold={threshold} />
      )}

      {candidate.why_it_matches && (
        <p className="text-body-sm text-ink-muted">
          {candidate.why_it_matches}
        </p>
      )}
      {!discovered && <Reasoning candidate={candidate} />}

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
        <p role="alert" className="text-body-sm text-danger">
          {failure}
        </p>
      )}

      {pending && deals === null && (
        <div className="flex flex-wrap gap-sm">
          <Button
            variant="secondary"
            disabled={decision.isPending}
            onClick={() => {
              approve();
            }}
          >
            Approve
          </Button>
          <Button
            variant="danger"
            disabled={decision.isPending}
            onClick={() => {
              decision.mutate({ kind: "reject" });
            }}
          >
            Reject
          </Button>
        </div>
      )}
      {!pending && candidate.deal_attio_id && (
        <p className="text-caption text-ink-subtle">
          Qualified deal in Attio{" "}
          <code className="font-mono text-mono">{candidate.deal_attio_id}</code>
        </p>
      )}
    </article>
  );
}
