import { useState } from "react";
import { useSearchParams } from "react-router";
import { BUYER_ACTIONS, BuyerDrawer, NEW_BUYER, checkSizeLabel, type BuyerPanel } from "../components/buyers/buyer-drawer";
import { BuyerFilters } from "../components/buyers/buyer-filters";
import { BuyerStatusPill } from "../components/buyers/buyer-status-pill";
import { ActionsMenu } from "../components/ui/actions-menu";
import { EmptyState } from "../components/ui/empty-state";
import { TextSearch } from "../components/ui/text-search";
import { CURRENT_USER_ID, addBuyer, addBuyerToDeal, getBuyersUniverse, updateBuyer } from "../demo/api";
import type { BuyerPatch } from "../demo/types";
import { matchesFilters, readBuyerFilters } from "../lib/buyer-filters";
import { matchesText } from "../lib/filters";
import { byId } from "../lib/by-id";
import type { Route } from "./+types/buyers-universe";

export async function clientLoader() {
  return getBuyersUniverse();
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  switch (field("intent")) {
    case "buyer-add":
      return addBuyer(CURRENT_USER_ID, JSON.parse(field("buyer")) as Parameters<typeof addBuyer>[1]);
    case "buyer-update":
      return updateBuyer(CURRENT_USER_ID, field("id"), JSON.parse(field("patch")) as BuyerPatch);
    case "add-to-deal":
      return addBuyerToDeal(CURRENT_USER_ID, field("id"), field("dealId"));
  }
}

export default function BuyersUniverse({ loaderData: data }: Route.ComponentProps) {
  const [adding, setAdding] = useState(false);
  const [params, setParams] = useSearchParams();
  const filters = readBuyerFilters(params);
  const query = params.get("q") ?? "";
  const buyers = data.buyers
    .filter((buyer) => matchesFilters(buyer, filters))
    .filter((buyer) => matchesText(query, [buyer.name, buyer.notes, buyer.hq, ...buyer.sectors, ...buyer.contactIds.map((id) => byId(data.people, id)?.name)]))
    .sort((a, b) => a.name.localeCompare(b.name));
  const openBuyer = byId(data.buyers, params.get("buyer") ?? undefined);
  const panel = BUYER_ACTIONS.find((action) => action.panel === params.get("panel"))?.panel ?? null;

  const show = (id: string, next: BuyerPanel | null) =>
    setParams(
      (url) => {
        url.set("buyer", id);
        if (next) url.set("panel", next);
        else url.delete("panel");
        return url;
      },
      { preventScrollReset: true },
    );
  const close = () =>
    setParams(
      (url) => {
        url.delete("buyer");
        url.delete("panel");
        return url;
      },
      { preventScrollReset: true },
    );

  return (
    <>
      <h1 className="page-title">Buyers universe</h1>
      <BuyerFilters buyers={data.buyers} shown={buyers.length} before={<TextSearch label="Search buyers" placeholder="Name, contact or note" />}>
        <button type="button" className="button" onClick={() => setAdding(true)}>
          Add buyer
        </button>
      </BuyerFilters>
      <div className="page-body">
        {buyers.length === 0 ? (
          <EmptyState>No buyers match these filters.</EmptyState>
        ) : (
          <div className="card card--flush">
            <table className="table table--fixed">
              <colgroup>
                <col style={{ width: "19%" }} />
                <col style={{ width: "11%" }} />
                <col style={{ width: "15%" }} />
                <col style={{ width: "11%" }} />
                <col style={{ width: "11%" }} />
                <col />
                <col style={{ width: "7%" }} />
                <col style={{ width: "10%" }} />
                <col style={{ width: "56px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Buyer</th>
                  <th scope="col">Type</th>
                  <th scope="col">Sectors</th>
                  <th scope="col">Geography</th>
                  <th scope="col" className="num">Check size</th>
                  <th scope="col">Key contact</th>
                  <th scope="col">Owner</th>
                  <th scope="col">Status</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {buyers.map((buyer) => {
                  const contact = byId(data.people, buyer.contactIds[0]);
                  return (
                    <tr key={buyer.id} className="row-clickable" tabIndex={0} onClick={() => show(buyer.id, null)} onKeyDown={(event) => event.key === "Enter" && show(buyer.id, null)}>
                      <td>
                        <span className="cell-title cell-clip">{buyer.name}</span>
                      </td>
                      <td>{buyer.type}</td>
                      <td className="cell-clip" title={buyer.sectors.join(", ")}>{buyer.sectors.join(", ")}</td>
                      <td className="cell-clip" title={buyer.geographies.join(", ")}>{buyer.geographies.join(", ")}</td>
                      <td className="num">{checkSizeLabel(buyer)}</td>
                      <td>
                        {contact ? (
                          <span className="cell-clip">{contact.name}</span>
                        ) : (
                          <span className="muted">No contact yet</span>
                        )}
                      </td>
                      <td>{byId(data.users, buyer.ownerId)?.name}</td>
                      <td>
                        <BuyerStatusPill status={buyer.status} />
                      </td>
                      <td>
                        <ActionsMenu itemName={buyer.name} actions={BUYER_ACTIONS} onPick={(next) => show(buyer.id, next)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {adding && <BuyerDrawer buyer={{ ...NEW_BUYER, ownerId: CURRENT_USER_ID }} data={data} panel="edit" onPanel={() => setAdding(false)} onClose={() => setAdding(false)} />}
      {openBuyer && (
        <BuyerDrawer key={`${openBuyer.id}-${panel}`} buyer={openBuyer} data={data} panel={panel} onPanel={(next) => show(openBuyer.id, next)} onClose={close} />
      )}
    </>
  );
}
