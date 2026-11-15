import { useSearchParams } from "react-router";
import { OpenToSellingPill } from "../components/sellers/open-to-selling-pill";
import { SELLER_ACTIONS, SellerDrawer, sellerActions, type SellerPanel } from "../components/sellers/seller-drawer";
import { ActionsMenu } from "../components/ui/actions-menu";
import { EmptyState } from "../components/ui/empty-state";
import { TextSearch } from "../components/ui/text-search";
import { FilterBar } from "../components/ui/filter-bar";
import { CURRENT_USER_ID, addSellerToDeal, createSellSideLead, getSellersUniverse, sendOwnerApproach, updateSeller } from "../demo/api";
import { OPEN_TO_SELLING, type SellerPatch } from "../demo/types";
import { byId } from "../lib/by-id";
import { matchesText, type FilterDef } from "../lib/filters";
import { formatDate, formatMoney } from "../lib/format";
import { matchesSellerFilters, readSellerFilters } from "../lib/seller-filters";
import type { Route } from "./+types/sellers-universe";

export async function clientLoader() {
  return getSellersUniverse();
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  switch (field("intent")) {
    case "seller-update":
      return updateSeller(CURRENT_USER_ID, field("id"), JSON.parse(field("patch")) as SellerPatch);
    case "add-to-deal":
      return addSellerToDeal(CURRENT_USER_ID, field("id"), field("dealId"));
    case "new-lead":
      return createSellSideLead(CURRENT_USER_ID, field("id"), field("codeName"), field("sector"), field("city"));
    case "approach":
      return sendOwnerApproach(field("id"), field("contactId"), field("summary"));
  }
}

export default function SellersUniverse({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const filters = readSellerFilters(params);
  const query = params.get("q") ?? "";
  const sellers = data.sellers
    .filter((seller) => matchesSellerFilters(seller, filters))
    .filter((seller) => matchesText(query, [seller.name, seller.notes, seller.hq, seller.sector, ...seller.contactIds.map((id) => byId(data.people, id)?.name)]))
    .sort((a, b) => a.name.localeCompare(b.name));
  const openSeller = byId(data.sellers, params.get("seller") ?? undefined);
  const panel = SELLER_ACTIONS.find((action) => action.panel === params.get("panel"))?.panel ?? null;

  const show = (id: string, next: SellerPanel | null) =>
    setParams(
      (url) => {
        url.set("seller", id);
        if (next) url.set("panel", next);
        else url.delete("panel");
        return url;
      },
      { preventScrollReset: true },
    );
  const close = () =>
    setParams(
      (url) => {
        url.delete("seller");
        url.delete("panel");
        return url;
      },
      { preventScrollReset: true },
    );

  const sorted = (values: string[]) => [...new Set(values)].sort();
  const filterDefs: FilterDef[] = [
    { kind: "list", key: "sector", label: "Sector", options: sorted(data.sellers.map((s) => s.sector)) },
    { kind: "list", key: "geography", label: "Geography", options: sorted(data.sellers.map((s) => s.geography)) },
    { kind: "range", key: "revenue", label: "Revenue" },
    { kind: "range", key: "ebitda", label: "EBITDA" },
    { kind: "list", key: "openToSelling", label: "Open to selling", options: [...OPEN_TO_SELLING] },
  ];

  return (
    <>
      <h1 className="page-title">Sellers universe</h1>
      <FilterBar before={<TextSearch label="Search sellers" placeholder="Name, owner or note" />} filters={filterDefs} shown={sellers.length} total={data.sellers.length} />
      <div className="page-body">
        {sellers.length === 0 ? (
          <EmptyState>No sellers match these filters.</EmptyState>
        ) : (
          <div className="card card--flush">
            <table className="table table--fixed">
              <colgroup>
                <col style={{ width: "18%" }} />
                <col style={{ width: "11%" }} />
                <col style={{ width: "8%" }} />
                <col style={{ width: "9%" }} />
                <col style={{ width: "9%" }} />
                <col />
                <col style={{ width: "10%" }} />
                <col style={{ width: "10%" }} />
                <col style={{ width: "6%" }} />
                <col style={{ width: "56px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Company</th>
                  <th scope="col">Sector</th>
                  <th scope="col">Geography</th>
                  <th scope="col" className="num">Revenue</th>
                  <th scope="col" className="num">EBITDA</th>
                  <th scope="col">Owner contact</th>
                  <th scope="col">Open to selling</th>
                  <th scope="col">Re-engage</th>
                  <th scope="col">Owner</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sellers.map((seller) => {
                  const contact = byId(data.people, seller.contactIds[0]);
                  return (
                    <tr key={seller.id} className="row-clickable" tabIndex={0} onClick={() => show(seller.id, null)} onKeyDown={(event) => event.key === "Enter" && show(seller.id, null)}>
                      <td>
                        <span className="cell-title cell-clip">{seller.name}</span>
                      </td>
                      <td className="cell-clip">{seller.sector}</td>
                      <td>{seller.geography}</td>
                      <td className="num">{formatMoney(seller.estRevenueUsd)}</td>
                      <td className="num">{formatMoney(seller.estEbitdaUsd)}</td>
                      <td>
                        {contact ? (
                          <span className="cell-clip">{contact.name}</span>
                        ) : (
                          <span className="muted">No contact yet</span>
                        )}
                      </td>
                      <td>
                        <OpenToSellingPill value={seller.openToSelling} />
                      </td>
                      <td>{seller.reEngageDate ? formatDate(seller.reEngageDate) : <span className="muted">Not set</span>}</td>
                      <td>{byId(data.users, seller.ownerId)?.name}</td>
                      <td>
                        <ActionsMenu itemName={seller.name} actions={sellerActions(seller)} onPick={(next) => show(seller.id, next)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {openSeller && (
        <SellerDrawer key={`${openSeller.id}-${panel}`} seller={openSeller} data={data} panel={panel} onPanel={(next) => show(openSeller.id, next)} onClose={close} />
      )}
    </>
  );
}
