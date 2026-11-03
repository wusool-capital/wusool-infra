import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";

import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/ui/button";
import { BuyerSearch } from "@/features/find-match/BuyerSearch";
import { ProfileCheck } from "@/features/find-match/ProfileCheck";
import { StepPanel } from "@/features/find-match/StepPanel";
import { StepsBar } from "@/features/find-match/StepsBar";
import { preRunSteps } from "@/features/find-match/steps";
import { useStartMatchRun } from "@/gen/hooks/useStartMatchRun";
import type { BuyerSummary } from "@/gen/types/BuyerSummary";
import { rememberRun } from "@/lib/recent-runs";

const searchSchema = z.object({ q: z.string().optional().catch(undefined) });

export const Route = createFileRoute("/_app/find-match")({
  validateSearch: searchSchema,
  component: FindMatchPage,
});

const UPCOMING = {
  match: "Scores every eligible seller against the mandate",
  shortlist: "Approve or reject each candidate",
  discovery: "Searches outside the CRM if every score is low",
  export: "Download the shortlist as CSV",
} as const;

function FindMatchPage(): React.JSX.Element {
  const { q } = Route.useSearch();
  const navigate = useNavigate();
  const [buyer, setBuyer] = useState<BuyerSummary | null>(null);
  const start = useStartMatchRun();
  const steps = preRunSteps(buyer === null ? "buyer" : "check");

  const run = (advisorContext: string | null): void => {
    if (buyer === null) return;
    start.mutate(
      { body: { buyer_role_id: buyer.id, advisor_context: advisorContext } },
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
    <>
      <TopBar crumbs={[{ label: "Tools", to: "/" }, { label: "Find match" }]} />
      <StepsBar steps={steps} />
      <main
        id="main"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-[760px] flex-col gap-lg px-md py-xl outline-none md:px-xl"
      >
        <h1 className="text-headline text-balance">New find-match run</h1>
        <ol className="flex flex-col gap-sm">
          <StepPanel
            id="buyer"
            state={steps.buyer}
            summary={buyer?.organization.name ?? "Pick the buyer to match"}
          >
            {buyer === null ? (
              <BuyerSearch initialQuery={q ?? ""} onPick={setBuyer} />
            ) : (
              <Button
                variant="secondary"
                className="self-start"
                onClick={() => {
                  setBuyer(null);
                  start.reset();
                }}
              >
                Change buyer
              </Button>
            )}
          </StepPanel>
          <StepPanel
            id="check"
            state={steps.check}
            summary={
              buyer === null
                ? "Checks the buyer's profile against your note"
                : "Add a note, then check"
            }
          >
            {buyer === null ? undefined : (
              <ProfileCheck
                key={buyer.id}
                buyer={buyer}
                starting={start.isPending}
                startError={start.isError ? start.error.message : null}
                onRun={run}
              />
            )}
          </StepPanel>
          <StepPanel id="match" state="upcoming" summary={UPCOMING.match} />
          <StepPanel
            id="shortlist"
            state="upcoming"
            summary={UPCOMING.shortlist}
          />
          <StepPanel
            id="discovery"
            state="upcoming"
            summary={UPCOMING.discovery}
          />
          <StepPanel id="export" state="upcoming" summary={UPCOMING.export} />
        </ol>
      </main>
    </>
  );
}
