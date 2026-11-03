import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { z } from "zod";

import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { BuyerSearch } from "@/features/find-match/BuyerSearch";
import { ProfileCheck } from "@/features/find-match/ProfileCheck";
import { StepsBar } from "@/features/find-match/StepsBar";
import {
  preRunSteps,
  STEP_LABELS,
  STEP_ORDER,
  type StepId,
} from "@/features/find-match/steps";
import { useStartMatchRun } from "@/gen/hooks/useStartMatchRun";
import type { BuyerSummary } from "@/gen/types/BuyerSummary";
import { rememberRun } from "@/lib/recent-runs";

const searchSchema = z.object({ q: z.string().optional().catch(undefined) });

export const Route = createFileRoute("/_app/find-match")({
  validateSearch: searchSchema,
  component: FindMatchPage,
});

const STEP_HELP: Record<StepId, string> = {
  buyer: "Pick the buyer whose mandate we're matching.",
  check: "Compares the CRM's profile with your note before anything runs.",
  match: "Scores every eligible CRM seller against the mandate.",
  shortlist: "Approve each candidate into Attio, or reject it.",
  discovery: "Searches Google Maps for new sellers if every score is low.",
  export: "Download the shortlist and every decision as CSV.",
};

function Mandate({ buyer }: { buyer: BuyerSummary | null }): React.JSX.Element {
  if (buyer === null) {
    return (
      <ol className="flex flex-col rounded-lg border border-hairline bg-surface-1">
        {STEP_ORDER.map((id) => (
          <li
            key={id}
            className="flex flex-col gap-[2px] border-b border-hairline px-md py-[10px] last:border-b-0"
          >
            <span className="text-body font-medium text-ink">
              {STEP_LABELS[id]}
            </span>
            <span className="text-small text-ink-subtle">{STEP_HELP[id]}</span>
          </li>
        ))}
      </ol>
    );
  }
  const focus = buyer.organization.sector_focus ?? [];
  const rows: [string, string | null | undefined][] = [
    ["Target vertical", buyer.target_vertical],
    ["Headquarters", buyer.organization.hq_country],
    ["Buyer model", buyer.model],
    ["Mandate status", buyer.mandate_status],
    ["Sector focus", focus.length > 0 ? focus.join(", ") : null],
  ];
  return (
    <dl className="flex flex-col rounded-lg border border-hairline bg-surface-1">
      {rows.map(([label, value]) => (
        <div
          key={label}
          className="flex items-baseline justify-between gap-md border-b border-hairline px-md py-[10px] last:border-b-0"
        >
          <dt className="text-body text-ink-subtle">{label}</dt>
          <dd
            className={
              value
                ? "text-right text-body text-ink"
                : "text-body text-ink-subtle"
            }
          >
            {value ?? "—"}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function FindMatchPage(): React.JSX.Element {
  const { q } = Route.useSearch();
  const navigate = useNavigate();
  const [buyer, setBuyer] = useState<BuyerSummary | null>(null);
  const start = useStartMatchRun();
  // Same buyer and note reuse one request id, so a double click or retry starts one run.
  const requestIds = useRef(new Map<string, string>());
  const steps = preRunSteps(buyer === null ? "buyer" : "check");

  const run = (advisorContext: string | null): void => {
    if (buyer === null) return;
    const key = `${buyer.id}\n${advisorContext ?? ""}`;
    const requestId = requestIds.current.get(key) ?? crypto.randomUUID();
    requestIds.current.set(key, requestId);
    start.mutate(
      {
        body: {
          buyer_role_id: buyer.id,
          advisor_context: advisorContext,
          request_id: requestId,
        },
      },
      {
        onSuccess: ({ run_id }) => {
          rememberRun({
            runId: run_id,
            buyerName: buyer.organization.name,
            advisorContext,
            startedAt: new Date().toISOString(),
          });
          void navigate({ to: "/runs/$runId", params: { runId: run_id } });
        },
      },
    );
  };

  return (
    <main
      id="main"
      tabIndex={-1}
      className="mx-auto flex w-full max-w-[1360px] flex-col gap-lg px-md py-lg outline-none md:px-xl md:py-xl"
    >
      <PageHeader
        parent={{ label: "Find match", to: "/" }}
        title={buyer?.organization.name ?? "New run"}
        sub={
          buyer === null
            ? "Pick the buyer whose mandate we're matching sellers against."
            : "Add what you know about their mandate, check it, then run the match."
        }
      />
      <StepsBar steps={steps} />

      <div className="grid items-start gap-xl lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-lg">
        <div className="flex min-w-0 flex-col gap-xl">
          <section
            aria-labelledby="buyer-title"
            className="flex flex-col gap-sm"
          >
            <h2 id="buyer-title" className="text-section">
              Buyer
            </h2>
            {buyer === null ? (
              <BuyerSearch initialQuery={q ?? ""} onPick={setBuyer} />
            ) : (
              <div className="flex items-center justify-between gap-md rounded-lg border border-hairline bg-surface-1 px-md py-sm">
                <span className="min-w-0 truncate text-body font-medium">
                  {buyer.organization.name}
                </span>
                <Button
                  variant="tertiary"
                  size="sm"
                  onClick={() => {
                    setBuyer(null);
                    start.reset();
                  }}
                >
                  Change
                </Button>
              </div>
            )}
          </section>

          {buyer !== null && (
            <section
              aria-labelledby="check-title"
              className="flex animate-rise flex-col gap-sm"
            >
              <h2 id="check-title" className="text-section">
                Profile check
              </h2>
              <ProfileCheck
                key={buyer.id}
                buyer={buyer}
                starting={start.isPending}
                startError={start.isError ? start.error.message : null}
                onRun={run}
              />
            </section>
          )}
        </div>

        <aside aria-labelledby="mandate-title" className="flex flex-col gap-sm">
          <h2 id="mandate-title" className="text-section">
            {buyer === null ? "How a run works" : "Mandate on file"}
          </h2>
          <Mandate buyer={buyer} />
        </aside>
      </div>
    </main>
  );
}
