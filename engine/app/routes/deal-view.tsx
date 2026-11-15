import { CaretLeft } from "@phosphor-icons/react";
import { Link, useLocation, useSearchParams } from "react-router";
import { BuyersTab } from "../components/mandates/buyers-tab";
import { DealOverview } from "../components/mandates/deal-overview";
import { DealPanel } from "../components/mandates/deal-panel";
import { HistoryTab } from "../components/mandates/history-tab";
import { MaterialsTab } from "../components/mandates/materials-tab";
import { OffersTab } from "../components/mandates/offers-tab";
import {
  CURRENT_USER_ID,
  addOffer,
  addSuggestions,
  emailClient,
  enrichCounterparty,
  getDealView,
  logDecision,
  requestClientDocuments,
  sendCim,
  sendEngagementLetter,
  sendOutreach,
  setMaterialStatus,
  setOfferStatus,
  updateCounterparty,
} from "../demo/api";
import type { CounterpartyStatus, MaterialStatus, OfferInput, OfferStatus } from "../demo/types";
import type { Route } from "./+types/deal-view";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  return getDealView(params.dealId);
}

export async function clientAction({ request, params }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  const dealId = params.dealId;

  switch (field("intent")) {
    case "counterparty":
      return updateCounterparty(CURRENT_USER_ID, field("id"), JSON.parse(field("patch")) as { status?: CounterpartyStatus; nextStep?: string });
    case "add-suggestions":
      return addSuggestions(dealId, JSON.parse(field("ids")) as string[]);
    case "enrich":
      return enrichCounterparty(field("id"));
    case "outreach":
      return sendOutreach(field("id"), field("contactId"), field("template"), field("link"), field("summary"));
    case "send-cim":
      return sendCim(dealId);
    case "request-docs":
      return requestClientDocuments(dealId, JSON.parse(field("items")) as string[]);
    case "engagement-send":
      return sendEngagementLetter(CURRENT_USER_ID, dealId);
    case "material-status":
      return setMaterialStatus(field("id"), field("status") as MaterialStatus);
    case "add-offer":
      return addOffer(dealId, JSON.parse(field("offer")) as OfferInput);
    case "offer-status":
      return setOfferStatus(CURRENT_USER_ID, field("id"), field("status") as OfferStatus, field("why"));
    case "decision":
      return logDecision(CURRENT_USER_ID, dealId, field("text"), field("why"), field("counterpartyId") || undefined);
    case "email-client":
      return emailClient(dealId, field("recipient"));
  }
}

export const TABS = ["buyers", "materials", "offers", "history"] as const;
export type DealTab = (typeof TABS)[number];

export default function DealView({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const location = useLocation();

  if (!data) {
    return (
      <>
        <h1 className="page-title">Deal not found</h1>
        <section className="card">
          <p>This deal does not exist in the demo data.</p>
          <Link className="button" to="/pipeline">Back to Pipeline</Link>
        </section>
      </>
    );
  }

  const tab: DealTab = TABS.includes(params.get("tab") as DealTab) ? (params.get("tab") as DealTab) : "buyers";
  const tabLabel = (key: DealTab) => (key === "buyers" ? (data.deal.side === "sell" ? "Buyers" : "Targets") : key[0].toUpperCase() + key.slice(1));
  const selectTab = (key: DealTab) =>
    setParams(
      (next) => {
        next.set("tab", key);
        next.delete("panel");
        return next;
      },
      { preventScrollReset: true },
    );

  return (
    <>
      <p className="breadcrumb">
        {/* Returns to the board or list the deal was opened from, filters included. */}
        <Link className="breadcrumb__back" to={(location.state as { from?: string } | null)?.from ?? "/pipeline"}>
          <CaretLeft size={14} aria-hidden="true" />
          Pipeline
        </Link>
      </p>
      {/* Overview, tabs and each tab's toolbar stay fixed; only the content under them scrolls. */}
      <DealOverview data={data} />
      <div className="tabs" role="tablist" aria-label="Deal sections">
        {TABS.map((key) => (
          <button key={key} type="button" role="tab" className="tabs__tab" aria-selected={tab === key} onClick={() => selectTab(key)}>
            {tabLabel(key)}
          </button>
        ))}
      </div>
      <div className="page-body" role="tabpanel" aria-label={tabLabel(tab)}>
        {tab === "buyers" && <BuyersTab data={data} />}
        {tab === "materials" && <MaterialsTab data={data} />}
        {tab === "offers" && <OffersTab data={data} />}
        {tab === "history" && <HistoryTab data={data} />}
      </div>
      <DealPanel data={data} />
    </>
  );
}
