import { AlertTriangle, ArrowUpRight, Check, X } from "lucide-react";
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
          {deals.map((deal) => (
            <li
              key={deal.attio_id}
              className="flex flex-wrap items-center justify-between gap-sm border-t border-hairline py-xs"
            >
              <span className="flex flex-col">
                <span className="text-ink">{deal.name}</span>
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
  onDecided,
}: {
  runId: string;
  candidate: CandidateRead;
  threshold: number;
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
                  Website <ArrowUpRight aria-hidden className="size-3.5" />
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
              decision.mutate({ kind: "reject" }, { onSuccess: decided });
            }}
          >
            <X aria-hidden />
            Reject
          </Button>
        </div>
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
