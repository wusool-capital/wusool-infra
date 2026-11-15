import { useState } from "react";
import { useSearchParams } from "react-router";
import { checkSizeLabel } from "../components/buyers/buyer-drawer";
import { BuyerFilters } from "../components/buyers/buyer-filters";
import { LeadDrawer } from "../components/pipeline/lead-drawer";
import { DescribeBox } from "../components/ui/describe-box";
import { SearchSwitch } from "../components/ui/search-switch";
import { EmptyState } from "../components/ui/empty-state";
import { SearchActions } from "../components/ui/search-actions";
import { useRouteAction } from "../components/ui/toast";
import {
  CURRENT_USER_ID,
  ENRICH_COST_CREDITS,
  addCandidatesAsBuyers,
  addCandidatesToDeal,
  createBuySideLead,
  enrichCandidates,
  searchBuyers,
} from "../demo/api";
import { BUYER_TYPES, type BuyerResult } from "../demo/types";
import { readBuyerFilters } from "../lib/buyer-filters";
import { filtersFromDescription } from "../lib/describe";
import { byId } from "../lib/by-id";
import { count } from "../lib/format";
import type { Route } from "./+types/buyers-search";

// Results exist only after Search, because once live each run calls Toolkit matching and Apollo.
export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const params = new URL(request.url).searchParams;
  return searchBuyers(params.get("searched") ? readBuyerFilters(params) : null, params.get("q") ?? "");
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  const ids = JSON.parse(field("ids") || "[]") as string[];
  switch (field("intent")) {
    case "enrich":
      return enrichCandidates(ids);
    case "add-buyers":
      return addCandidatesAsBuyers(CURRENT_USER_ID, ids);
    case "add-to-deal":
      return addCandidatesToDeal(CURRENT_USER_ID, ids, field("dealId"));
    case "new-lead":
      return createBuySideLead(CURRENT_USER_ID, ids[0], field("codeName"), field("sector"), field("city"));
  }
}

// Clear filters also drops the search already run and its sentence, so the page starts over.
const SEARCH_KEYS = ["searched", "ask", "q"];

export default function BuyersSearch({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const act = useRouteAction("/search/buyers");
  const [pickedIds, setPickedIds] = useState<string[]>([]);
  const [leadFor, setLeadFor] = useState<BuyerResult | null>(null);
  const results = data.results ?? [];
  const picked = results.filter((row) => pickedIds.includes(row.id));
  const toggle = (id: string) => setPickedIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  const allPicked = results.length > 0 && picked.length === results.length;

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
      sectors: [...new Set(data.profiles.flatMap((p) => p.sectors))],
      geographies: [...new Set(data.profiles.flatMap((p) => p.geographies))],
      types: [...BUYER_TYPES],
      amountKey: "checkSize",
      ebitdaKey: "minEbitda",
    });
    next.set("ask", text);
    next.set("searched", "1");
    setParams(next, { preventScrollReset: true });
  };

  const run = (intent: string, notice: string, extra: Record<string, string> = {}) => {
    act({ intent, ids: JSON.stringify(pickedIds), ...extra }, notice);
    setPickedIds([]);
  };
  const newNames = picked.filter((row) => !row.inAttio);
  const toEnrich = picked.filter((row) => !row.enriched);

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Search</h1>
        <SearchSwitch />
      </div>
      <DescribeBox
        label="Describe the buyers you want"
        placeholder="Describe the buyers you want, for example family offices in the UAE buying nurseries, then press Enter"
        initial={params.get("ask") ?? ""}
        key={params.get("ask") ?? ""}
        onSubmit={fillFromDescription}
      />
      <BuyerFilters buyers={data.profiles} alsoClear={SEARCH_KEYS}>
        <button type="button" className="button" onClick={search}>
          Search
        </button>
      </BuyerFilters>

      <div className="page-body">
        {data.results === null ? null : results.length === 0 ? (
          <EmptyState>No companies match.</EmptyState>
        ) : (
          <>
            <SearchActions
              picked={picked}
              deals={data.deals}
              creditsLeft={data.apolloCreditsLeft}
              roleNoun="buyer role"
              leadSide="buy"
              onEnrich={() => run("enrich", `${count(toEnrich.length, "company", "companies")} enriched for ${toEnrich.length * ENRICH_COST_CREDITS} credits.`)}
              onAddRoles={() => run("add-buyers", `${count(newNames.length, "buyer role", "buyer roles")} added to Attio. ${picked.length - newNames.length ? "Companies already in Attio were skipped." : ""}`.trim())}
              onAddToDeal={(dealId) => run("add-to-deal", `${count(picked.length, "company", "companies")} added to ${byId(data.deals, dealId)?.codeName} as not contacted.`, { dealId })}
              onNewLead={() => setLeadFor(picked[0])}
            />
            <div className="card card--flush">
              <table className="table table--fixed">
                <colgroup>
                  <col style={{ width: "40px" }} />
                  <col style={{ width: "22%" }} />
                  <col style={{ width: "9%" }} />
                  <col style={{ width: "13%" }} />
                  <col style={{ width: "10%" }} />
                  <col style={{ width: "12%" }} />
                  <col style={{ width: "9%" }} />
                  <col style={{ width: "8%" }} />
                  <col />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col">
                      <input
                        type="checkbox"
                        aria-label="Select all results"
                        checked={allPicked}
                        onChange={() => setPickedIds(allPicked ? [] : results.map((row) => row.id))}
                      />
                    </th>
                    <th scope="col">Company</th>
                    <th scope="col">Type</th>
                    <th scope="col">Sectors</th>
                    <th scope="col">Geography</th>
                    <th scope="col" className="num">Check size</th>
                    <th scope="col">Why</th>
                    <th scope="col">Attio</th>
                    <th scope="col">Contacts</th>
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
                      <td>{row.type}</td>
                      <td className="cell-clip">{row.sectors.join(", ")}</td>
                      <td className="cell-clip">{row.geographies.join(", ")}</td>
                      <td className="num">{checkSizeLabel(row)}</td>
                      <td className="cell-clip" title={row.rationale}>{row.rationale}</td>
                      <td>{row.inAttio ? <span className="badge">In Attio</span> : <span className="muted">New</span>}</td>
                      <td>
                        <ContactsCell row={row} data={data} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {leadFor && (
        <LeadDrawer
          side="buy"
          companyName={leadFor.name}
          defaults={{ codeName: data.nextCodeName, sector: leadFor.sectors[0] ?? "", city: leadFor.hq }}
          note={leadFor.rationale}
          onClose={() => setLeadFor(null)}
          onCreate={(fields) => {
            act({ intent: "new-lead", ids: JSON.stringify([leadFor.id]), ...fields }, `${fields.codeName} created as a buy-side lead in the Pipeline.`);
            setLeadFor(null);
            setPickedIds([]);
          }}
        />
      )}
    </>
  );
}

function ContactsCell({ row, data }: { row: BuyerResult; data: Route.ComponentProps["loaderData"] }) {
  if (!row.enriched) return <span className="muted cell-clip">{row.inAttio ? "Held in Attio" : "Not enriched"}</span>;
  const names = row.contactIds.map((id) => byId(data.people, id)?.name).filter(Boolean);
  return <span className="cell-clip">{names.join(", ")}</span>;
}
