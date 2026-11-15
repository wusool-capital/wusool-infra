import { useState } from "react";
import { useSearchParams } from "react-router";
import { LeadDrawer } from "../components/pipeline/lead-drawer";
import { AskOwnersDrawer, type OwnerNote } from "../components/sellers/ask-owners-drawer";
import { DescribeBox } from "../components/ui/describe-box";
import { SearchSwitch } from "../components/ui/search-switch";
import { EmptyState } from "../components/ui/empty-state";
import { FilterBar } from "../components/ui/filter-bar";
import { SearchActions } from "../components/ui/search-actions";
import { useRouteAction } from "../components/ui/toast";
import {
  CURRENT_USER_ID,
  ENRICH_COST_CREDITS,
  addCandidatesAsSellers,
  addSellerCandidatesToDeal,
  createSellSideLeadFromSearch,
  enrichSellerCandidates,
  searchSellers,
  sendOwnerApproaches,
} from "../demo/api";
import type { SellerResult } from "../demo/types";
import { byId } from "../lib/by-id";
import { filtersFromDescription } from "../lib/describe";
import type { FilterDef } from "../lib/filters";
import { count, formatDate, formatMoney } from "../lib/format";
import { readSellerFilters } from "../lib/seller-filters";
import type { Route } from "./+types/sellers-search";

// Results exist only after Search, because once live each run calls Toolkit discovery and Apollo.
export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const params = new URL(request.url).searchParams;
  return searchSellers(params.get("searched") ? readSellerFilters(params) : null, params.get("q") ?? "");
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  const ids = JSON.parse(field("ids") || "[]") as string[];
  switch (field("intent")) {
    case "enrich":
      return enrichSellerCandidates(ids);
    case "add-sellers":
      return addCandidatesAsSellers(CURRENT_USER_ID, ids);
    case "add-to-deal":
      return addSellerCandidatesToDeal(CURRENT_USER_ID, ids, field("dealId"));
    case "new-lead":
      return createSellSideLeadFromSearch(CURRENT_USER_ID, ids[0], field("codeName"), field("sector"), field("city"));
    case "ask-owners":
      return sendOwnerApproaches(CURRENT_USER_ID, JSON.parse(field("notes")) as OwnerNote[]);
  }
}

type Overlay = { kind: "lead"; row: SellerResult } | { kind: "ask"; rows: SellerResult[] } | null;

// Clear filters also drops the search already run and its sentence, so the page starts over.
const SEARCH_KEYS = ["searched", "ask", "q"];

export default function SellersSearch({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const act = useRouteAction("/search/sellers");
  const [pickedIds, setPickedIds] = useState<string[]>([]);
  const [overlay, setOverlay] = useState<Overlay>(null);
  const results = data.results ?? [];
  const picked = results.filter((row) => pickedIds.includes(row.id));
  const toggle = (id: string) => setPickedIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  const allPicked = results.length > 0 && picked.length === results.length;
  const newNames = picked.filter((row) => !row.inAttio);
  const toEnrich = picked.filter((row) => !row.enriched);

  const sorted = (values: string[]) => [...new Set(values)].sort();
  const filters: FilterDef[] = [
    { kind: "list", key: "sector", label: "Sector", options: sorted(data.profiles.map((p) => p.sector)) },
    { kind: "list", key: "geography", label: "Geography", options: sorted(data.profiles.map((p) => p.geography)) },
    { kind: "range", key: "revenue", label: "Revenue" },
  ];

  const search = () => {
    setPickedIds([]);
    setParams(
      (next) => {
        next.set("searched", "1");
        return next;
      },
      { preventScrollReset: true },
    );
  };

  // The sentence replaces the filters and keywords and runs the search; the filled filters light up.
  const fillFromDescription = (text: string) => {
    setPickedIds([]);
    const next = filtersFromDescription(text, {
      sectors: [...new Set(data.profiles.map((p) => p.sector))],
      geographies: [...new Set(data.profiles.map((p) => p.geography))],
      amountKey: "revenue",
    });
    next.set("ask", text);
    next.set("searched", "1");
    setParams(next, { preventScrollReset: true });
  };

  const run = (intent: string, notice: string, extra: Record<string, string> = {}) => {
    act({ intent, ids: JSON.stringify(pickedIds), ...extra }, notice);
    setPickedIds([]);
  };

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Search</h1>
        <SearchSwitch />
      </div>
      <DescribeBox
        label="Describe the owners you want"
        placeholder="Describe the owners you want, for example dental clinics in Riyadh with $3M to $10M revenue, then press Enter"
        initial={params.get("ask") ?? ""}
        key={params.get("ask") ?? ""}
        onSubmit={fillFromDescription}
      />
      <FilterBar filters={filters} alsoClear={SEARCH_KEYS}>
        <button type="button" className="button" onClick={search}>
          Search
        </button>
      </FilterBar>

      <div className="page-body">
        {data.results === null ? null : results.length === 0 ? (
          <EmptyState>No companies match.</EmptyState>
        ) : (
          <>
            <SearchActions
              picked={picked}
              deals={data.deals}
              creditsLeft={data.apolloCreditsLeft}
              roleNoun="seller role"
              leadSide="sell"
              onEnrich={() => run("enrich", `${count(toEnrich.length, "company", "companies")} enriched for ${toEnrich.length * ENRICH_COST_CREDITS} credits.`)}
              onAddRoles={() => run("add-sellers", `${count(newNames.length, "seller role", "seller roles")} added to Attio. ${picked.length - newNames.length ? "Companies already in Attio were skipped." : ""}`.trim())}
              onAddToDeal={(dealId) => run("add-to-deal", `${count(picked.length, "company", "companies")} added to ${byId(data.deals, dealId)?.codeName} as targets.`, { dealId })}
              onNewLead={() => setOverlay({ kind: "lead", row: picked[0] })}
            >
              <button type="button" className="button button--small" disabled={picked.length === 0} onClick={() => setOverlay({ kind: "ask", rows: picked })}>
                Ask if open to selling
              </button>
            </SearchActions>
            <div className="card card--flush">
              <table className="table table--fixed">
                <colgroup>
                  <col style={{ width: "40px" }} />
                  <col style={{ width: "26%" }} />
                  <col style={{ width: "11%" }} />
                  <col style={{ width: "8%" }} />
                  <col style={{ width: "8%" }} />
                  <col style={{ width: "8%" }} />
                  <col style={{ width: "9%" }} />
                  <col style={{ width: "8%" }} />
                  <col />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col">
                      <input type="checkbox" aria-label="Select all results" checked={allPicked} onChange={() => setPickedIds(allPicked ? [] : results.map((row) => row.id))} />
                    </th>
                    <th scope="col">Company</th>
                    <th scope="col">Sector</th>
                    <th scope="col">Geography</th>
                    <th scope="col" className="num">Revenue</th>
                    <th scope="col" className="num">Employees</th>
                    <th scope="col">Why</th>
                    <th scope="col">Attio</th>
                    <th scope="col">Owner contact</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((row) => (
                    <tr key={row.id} className="row-clickable" onClick={() => toggle(row.id)}>
                      <td>
                        <input type="checkbox" aria-label={`Select ${row.name}`} checked={pickedIds.includes(row.id)} onChange={() => toggle(row.id)} onClick={(event) => event.stopPropagation()} />
                      </td>
                      <td>
                        <span className="cell-title cell-clip">{row.name}</span>
                      </td>
                      <td className="cell-clip">{row.sector}</td>
                      <td>{row.geography}</td>
                      <td className="num">{formatMoney(row.estRevenueUsd)}</td>
                      <td className="num">{row.employees}</td>
                      <td className="cell-clip" title={row.rationale}>{row.rationale}</td>
                      <td>{row.inAttio ? <span className="badge">In Attio</span> : <span className="muted">New</span>}</td>
                      <td>
                        <OwnerCell row={row} data={data} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {overlay?.kind === "lead" && (
        <LeadDrawer
          side="sell"
          companyName={overlay.row.name}
          defaults={{ codeName: data.nextCodeName, sector: overlay.row.sector, city: overlay.row.hq }}
          note={overlay.row.rationale}
          onClose={() => setOverlay(null)}
          onCreate={(fields) => {
            act({ intent: "new-lead", ids: JSON.stringify([overlay.row.id]), ...fields }, `${fields.codeName} created as a sell-side lead in the Pipeline.`);
            setOverlay(null);
            setPickedIds([]);
          }}
        />
      )}
      {overlay?.kind === "ask" && (
        <AskOwnersDrawer
          rows={overlay.rows}
          people={data.people}
          onClose={() => setOverlay(null)}
          onSend={(notes) => {
            act({ intent: "ask-owners", notes: JSON.stringify(notes) }, `${count(notes.length, "note", "notes")} sent. Follow-ups are in Outreach. Demo: nothing was sent.`);
            setOverlay(null);
            setPickedIds([]);
          }}
        />
      )}
    </>
  );
}

function OwnerCell({ row, data }: { row: SellerResult; data: Route.ComponentProps["loaderData"] }) {
  const owner = byId(data.people, row.contactIds[0]);
  if (row.approachedOn) return <span className="muted cell-clip">Asked {formatDate(row.approachedOn)}</span>;
  if (owner) return <span className="cell-clip">{owner.name}</span>;
  return <span className="muted cell-clip">{row.inAttio ? "No contact in Attio" : "Not enriched"}</span>;
}
