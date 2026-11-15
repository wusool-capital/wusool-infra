import { useSearchParams } from "react-router";
import { OpenToSellingPill } from "../components/sellers/open-to-selling-pill";
import { SELLER_ACTIONS, SellerDrawer, sellerActions, type SellerPanel } from "../components/sellers/seller-drawer";
import { ActionsMenu } from "../components/ui/actions-menu";
import { EmptyState } from "../components/ui/empty-state";
import { TextSearch } from "../components/ui/text-search";
import { FilterBar } from "../components/ui/filter-bar";
import { CURRENT_USER_ID, addSellerToDeal, createSellSideLead, getSellersUniverse, sendOwnerApproach, updateSeller } from "../api";
import { OPEN_TO_SELLING, type SellerPatch } from "../demo/types";
import { attempt } from "../lib/action-result";
import { byId } from "../lib/by-id";
import type { FilterDef } from "../lib/filters";
import { formatDate, formatMoney } from "../lib/format";
import { reloadOnFilterChange } from "../lib/revalidate";
import { useMorePages } from "../lib/use-more-pages";
import type { Route } from "./+types/sellers-universe";

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return getSellersUniverse(new URL(request.url).searchParams);
}

export const shouldRevalidate = reloadOnFilterChange(["q", "sector", "geography", "revenue", "ebitda", "openToSelling"]);

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  return attempt(async () => {
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
  });
}

export default function SellersUniverse({ loaderData: initial }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  // The Toolkit filters, searches and sorts; "Show more" adds the following pages to the first.
  const { pages, hasMore, loading, failed, showMore } = useMorePages(initial, (cursor) => getSellersUniverse(params, cursor));
  const sellers = pages.flatMap((page) => page.sellers);
  const data = { ...initial, sellers, people: pages.flatMap((page) => page.people) };
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

  const filterDefs: FilterDef[] = [
    { kind: "list", key: "sector", label: "Sector", options: data.options.sectors },
    { kind: "list", key: "geography", label: "Geography", options: data.options.geographies },
    { kind: "range", key: "revenue", label: "Revenue" },
    { kind: "range", key: "ebitda", label: "EBITDA" },
    { kind: "list", key: "openToSelling", label: "Open to selling", options: [...OPEN_TO_SELLING] },
  ];

  return (
    <>
      <h1 className="page-title">Sellers universe</h1>
      <FilterBar before={<TextSearch label="Search sellers" placeholder="Name, owner or note" />} filters={filterDefs} shown={data.matched} total={data.total} />
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
            {hasMore && (
              <div className="table-more">
                <button type="button" className="button button--quiet" disabled={loading} onClick={() => void showMore()}>
                  {loading ? "Loading" : `Show more (${sellers.length} of ${data.matched})`}
                </button>
                {failed && <span className="field-error">Could not load more. Try again.</span>}
              </div>
            )}
          </div>
        )}
      </div>
      {openSeller && (
        <SellerDrawer key={`${openSeller.id}-${panel}`} seller={openSeller} data={data} panel={panel} onPanel={(next) => show(openSeller.id, next)} onClose={close} />
      )}
    </>
  );
}
