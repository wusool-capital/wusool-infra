import { useState } from "react";
import { useSearchParams } from "react-router";
import { NEW_PARTNER, PARTNER_ACTIONS, PartnerDrawer, type PartnerPanel } from "../components/partners/partner-drawer";
import { PartnerLogo } from "../components/partners/partner-logo";
import { ActionsMenu } from "../components/ui/actions-menu";
import { EmptyState } from "../components/ui/empty-state";
import { FilterBar } from "../components/ui/filter-bar";
import { CURRENT_USER_ID, createReferredLead, getPartners, publishPartner } from "../demo/api";
import type { PartnerPublic, PartnerTerms } from "../demo/types";
import { byId } from "../lib/by-id";
import { anyOf, readList } from "../lib/filters";
import type { Route } from "./+types/partners";
import { Segmented } from "../components/ui/segmented";

export async function clientLoader() {
  return getPartners();
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  switch (field("intent")) {
    case "publish":
      return publishPartner(CURRENT_USER_ID, field("id"), JSON.parse(field("fields")) as PartnerPublic, JSON.parse(field("terms")) as PartnerTerms);
    case "lead":
      return createReferredLead(CURRENT_USER_ID, field("id"), field("clientName"), field("codeName"), field("sector"), field("city"));
  }
}

// Active partners are listed on the public website; inactive ones are kept but not shown.
const STATUSES = ["Active", "Inactive"];

export default function Partners({ loaderData: data }: Route.ComponentProps) {
  const [adding, setAdding] = useState(false);
  const [params, setParams] = useSearchParams();
  const categories = readList(params, "category");
  const statuses = readList(params, "status");
  const rows = data.partners.filter((partner) => anyOf(categories, [partner.category]) && anyOf(statuses, [partner.active ? "Active" : "Inactive"]));
  const openPartner = byId(data.partners, params.get("partner") ?? undefined);
  const view = params.get("view") === "list" ? "list" : "grid";
  const panel = PARTNER_ACTIONS.find((action) => action.panel === params.get("panel"))?.panel ?? null;

  const show = (id: string, next: PartnerPanel | null) =>
    setParams(
      (url) => {
        url.set("partner", id);
        if (next) url.set("panel", next);
        else url.delete("panel");
        return url;
      },
      { preventScrollReset: true },
    );
  const close = () =>
    setParams(
      (url) => {
        url.delete("partner");
        url.delete("panel");
        return url;
      },
      { preventScrollReset: true },
    );

  return (
    <>
      <h1 className="page-title">Referral partners</h1>
      <FilterBar
        shown={rows.length}
        total={data.partners.length}
        before={
          <Segmented role="group" aria-label="View">
            {(["grid", "list"] as const).map((value) => (
              <button
                key={value}
                type="button"
                className="segmented__option"
                aria-pressed={view === value}
                onClick={() =>
                  setParams(
                    (url) => {
                      url.set("view", value);
                      return url;
                    },
                    { preventScrollReset: true },
                  )
                }
              >
                {value === "grid" ? "Grid" : "List"}
              </button>
            ))}
          </Segmented>
        }
        filters={[
          { kind: "list", key: "category", label: "Category", options: [...new Set(data.partners.map((partner) => partner.category))].sort() },
          { kind: "list", key: "status", label: "Status", options: STATUSES },
        ]}
      >
        <button type="button" className="button" onClick={() => setAdding(true)}>
          Add partner
        </button>
      </FilterBar>
      <div className="page-body">
        {rows.length === 0 ? (
          <EmptyState>No partners match these filters.</EmptyState>
        ) : view === "grid" ? (
          <ul className="partner-grid">
            {/* The card is the mouse target; the name is the keyboard target, so no button sits inside another. */}
            {rows.map((partner) => {
              const leads = data.deals.filter((deal) => deal.sourcePartnerId === partner.id);
              return (
                <li key={partner.id}>
                  <div className="partner-card" onClick={() => show(partner.id, null)}>
                    <div className="partner-card__head">
                      <PartnerLogo name={partner.name} />
                      <div className="partner-card__titles">
                        <button type="button" className="partner-card__name" onClick={(event) => (event.stopPropagation(), show(partner.id, null))}>
                          {partner.name}
                        </button>
                        <p className="partner-card__category">{partner.category}</p>
                      </div>
                      <ActionsMenu itemName={partner.name} actions={PARTNER_ACTIONS} onPick={(next) => show(partner.id, next)} />
                    </div>
                    <p className="partner-card__offer">{partner.offer}</p>
                    <p className="partner-card__meta">
                      {partner.referralType} {partner.referral}
                    </p>
                    <div className="partner-card__foot">
                      <span className={partner.active ? "pill pill--closed" : "pill pill--not-started"}>{partner.active ? "Active" : "Inactive"}</span>
                      <span className="muted">
                        {leads.length} {leads.length === 1 ? "lead" : "leads"}, {leads.filter((deal) => deal.status === "Active").length} open
                      </span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="card card--flush">
            <table className="table table--fixed">
              <colgroup>
                <col style={{ width: "18%" }} />
                <col />
                <col style={{ width: "16%" }} />
                <col style={{ width: "11%" }} />
                <col style={{ width: "7%" }} />
                <col style={{ width: "7%" }} />
                <col style={{ width: "8%" }} />
                <col style={{ width: "56px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Partner</th>
                  <th scope="col">Offer</th>
                  <th scope="col">Referral</th>
                  <th scope="col">Locations</th>
                  <th scope="col" className="num">Leads</th>
                  <th scope="col" className="num">Open</th>
                  <th scope="col">Website</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((partner) => {
                  const leads = data.deals.filter((deal) => deal.sourcePartnerId === partner.id);
                  return (
                    <tr key={partner.id} className="row-clickable" tabIndex={0} onClick={() => show(partner.id, null)} onKeyDown={(event) => event.key === "Enter" && show(partner.id, null)}>
                      <td>
                        <span className="partner-cell">
                          <PartnerLogo name={partner.name} size="small" />
                          <span className="cell-title cell-clip">{partner.name}</span>
                        </span>
                      </td>
                      <td className="cell-clip">{partner.offer}</td>
                      <td className="cell-clip">{partner.referral}</td>
                      <td className="cell-clip">{partner.locations.join(", ")}</td>
                      <td className="num">{leads.length}</td>
                      <td className="num">{leads.filter((deal) => deal.status === "Active").length}</td>
                      <td>
                        <span className={partner.active ? "pill pill--closed" : "pill pill--not-started"}>{partner.active ? "Active" : "Inactive"}</span>
                      </td>
                      <td>
                        <ActionsMenu itemName={partner.name} actions={PARTNER_ACTIONS} onPick={(next) => show(partner.id, next)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {adding && <PartnerDrawer partner={NEW_PARTNER} data={data} panel="edit" onPanel={() => setAdding(false)} onClose={() => setAdding(false)} />}
      {openPartner && <PartnerDrawer key={`${openPartner.id}-${panel}`} partner={openPartner} data={data} panel={panel} onPanel={(next) => show(openPartner.id, next)} onClose={close} />}
    </>
  );
}
