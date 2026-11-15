import { useState } from "react";
import { useSearchParams } from "react-router";
import { DealDrawer } from "../components/pipeline/deal-drawer";
import { DealTable } from "../components/pipeline/deal-table";
import { KanbanBoard } from "../components/pipeline/kanban-board";
import { NewDealDrawer } from "../components/pipeline/new-deal-drawer";
import { PipelineToolbar, readFilters } from "../components/pipeline/pipeline-toolbar";
import { CURRENT_USER_ID, approveBlurb, createDeal, getPipeline, updateDeal } from "../demo/api";
import { useRouteAction } from "../components/ui/toast";
import type { DealPatch, NewDealInput } from "../demo/types";
import { byId } from "../lib/by-id";
import { anyOf, matchesText } from "../lib/filters";
import { formatMoney } from "../lib/format";
import type { Route } from "./+types/pipeline";

export async function clientLoader() {
  return getPipeline();
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");

  switch (field("intent")) {
    case "deal-update":
      return updateDeal(CURRENT_USER_ID, field("id"), JSON.parse(field("patch")) as DealPatch);
    case "blurb-approve":
      return approveBlurb(field("id"), field("blurb"));
    case "new-deal":
      return createDeal(CURRENT_USER_ID, JSON.parse(field("deal")) as NewDealInput);
  }
}

export default function Pipeline({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params, data.currentUserId);
  const query = params.get("q") ?? "";
  const deals = data.deals.filter(
    (deal) =>
      anyOf(filters.sides, [deal.side]) &&
      anyOf(filters.statuses, [deal.status]) &&
      anyOf(filters.owners, [deal.ownerId]) &&
      matchesText(query, [deal.codeName, deal.clientName]),
  );
  const openDeal = byId(data.deals, params.get("deal") ?? undefined);
  const act = useRouteAction("/pipeline");
  const [creating, setCreating] = useState(false);

  const closeDrawer = () =>
    setParams(
      (next) => {
        next.delete("deal");
        return next;
      },
      { preventScrollReset: true },
    );

  return (
    <>
      <h1 className="page-title">Pipeline</h1>
      <PipelineFacts deals={data.deals} />
      <PipelineToolbar filters={filters} users={data.users} currentUserId={data.currentUserId} count={deals.length} total={data.deals.length} onNewDeal={() => setCreating(true)} />
      <div className="page-body">
        {filters.view === "board" ? (
          <KanbanBoard deals={deals} users={data.users} />
        ) : (
          <DealTable deals={deals} users={data.users} counts={data.counts} now={data.now} />
        )}
      </div>
      {creating && (
        <NewDealDrawer
          clients={data.clients}
          nextCodeName={data.nextCodeName}
          onClose={() => setCreating(false)}
          onCreate={(input) => {
            act({ intent: "new-deal", deal: JSON.stringify(input) }, `${input.codeName} created at Lead.`);
            setCreating(false);
          }}
        />
      )}
      {openDeal && (
        <DealDrawer
          key={openDeal.id}
          next={data.nextActions[openDeal.id]}
          deal={openDeal}
          users={data.users}
          people={data.people}
          now={data.now}
          onClose={closeDrawer}
        />
      )}
    </>
  );
}

/** The page's one fact line: firm-wide, so it does not move with the filters. */
function PipelineFacts({ deals }: { deals: Route.ComponentProps["loaderData"]["deals"] }) {
  const active = deals.filter((deal) => deal.status === "Active");
  const inPlay = active.reduce((sum, deal) => sum + (deal.valueUsd ?? 0), 0);
  return (
    <p className="page-meta">
      {deals.length} deals · {active.length} active · {formatMoney(inPlay)} in active deals
    </p>
  );
}
