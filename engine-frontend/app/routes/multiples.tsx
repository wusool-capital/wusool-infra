import { useState } from "react";
import { useSearchParams } from "react-router";
import { DescribeBox } from "../components/ui/describe-box";
import { EmptyState } from "../components/ui/empty-state";
import { FilterBar } from "../components/ui/filter-bar";
import { useRouteAction } from "../components/ui/toast";
import { CURRENT_USER_ID, getMultiples, saveComparable } from "../demo/api";
import type { Comparable } from "../demo/types";
import type { FilterDef } from "../lib/filters";
import { formatDate, formatMoney } from "../lib/format";
import { MULTIPLES, filtersFromQuestion, formatMultiple, matchesMultipleFilters, median, multipleOf, readMultipleFilters } from "../lib/multiples";
import type { Route } from "./+types/multiples";
import { Segmented } from "../components/ui/segmented";

export async function clientLoader() {
  return getMultiples();
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  if (form.get("intent") === "save") return saveComparable(CURRENT_USER_ID, String(form.get("id")));
}

// Below this many database matches, a web search runs as a fallback (PRD MU4).
const MIN_DATABASE_MATCHES = 5;
const THIS_YEAR = 2026;

// Clear filters also drops the search already run and its sentence, so the page starts over.
const SEARCH_KEYS = ["searched", "ask", "q"];

export default function Multiples({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const act = useRouteAction("/multiples");
  const [excluded, setExcluded] = useState<string[]>([]);
  const filters = readMultipleFilters(params);
  const searched = params.has("searched");
  const matches = data.comparables.filter((row) => matchesMultipleFilters(row, filters));
  const database = matches.filter((row) => row.verified).sort((a, b) => b.date.localeCompare(a.date));
  const web = database.length < MIN_DATABASE_MATCHES ? matches.filter((row) => !row.verified) : [];
  // Web numbers never enter the median (MU4); excluded rows leave it too (MU3).
  const values = database.filter((row) => !excluded.includes(row.id)).map((row) => multipleOf(row, filters.multiple));
  const mid = median(values);

  const sorted = (items: string[]) => [...new Set(items)].sort();
  const filterDefs: FilterDef[] = [
    { kind: "list", key: "sector", label: "Sector", options: sorted(data.comparables.map((row) => row.sector)) },
    { kind: "list", key: "geography", label: "Geography", options: sorted(data.comparables.map((row) => row.geography)) },
    { kind: "range", key: "size", label: "Deal size" },
    { kind: "list", key: "year", label: "Year", options: sorted(data.comparables.map((row) => row.date.slice(0, 4))).reverse() },
    { kind: "list", key: "type", label: "Deal type", options: ["Strategic", "Sponsor"] },
  ];

  const setMultiple = (value: string) =>
    setParams(
      (next) => {
        next.set("multiple", value);
        return next;
      },
      { preventScrollReset: true },
    );
  const showResults = () => {
    setExcluded([]);
    setParams(
      (next) => {
        next.set("searched", "1");
        return next;
      },
      { preventScrollReset: true },
    );
  };
  const fillFromQuestion = (question: string) => {
    setExcluded([]);
    const next = filtersFromQuestion(question, THIS_YEAR);
    next.set("ask", question);
    next.set("searched", "1");
    setParams(next, { preventScrollReset: true });
  };

  return (
    <>
      <h1 className="page-title">Multiples</h1>
      <DescribeBox
        label="Which multiples are you looking for?"
        placeholder="Which multiples? For example EV/EBITDA for GCC veterinary clinics under $20M, last 3 years. Press Enter"
        initial={params.get("ask") ?? ""}
        key={params.get("ask") ?? ""}
        onSubmit={fillFromQuestion}
      />

      <FilterBar
        alsoClear={SEARCH_KEYS}
        before={
          <Segmented role="group" aria-label="Multiple">
            {MULTIPLES.map((value) => (
              <button key={value} type="button" className="segmented__option" aria-pressed={filters.multiple === value} onClick={() => setMultiple(value)}>
                {value}
              </button>
            ))}
          </Segmented>
        }
        filters={filterDefs}
      >
        <button type="button" className="button" onClick={showResults}>
          Show results
        </button>
      </FilterBar>

      <div className="page-body">
        {!searched ? (
          null
        ) : (
          <>
            <section className="card" aria-labelledby="db-title">
              <div className="card__head">
                <h2 id="db-title" className="section-title">Database</h2>
                <span className="card__meta">Reviewed by an advisor, with a source. Only these go into client documents.</span>
              </div>
              <dl className="figures">
                <Figure label={`Median ${filters.multiple}`} value={mid === undefined ? "Not set" : formatMultiple(mid)} />
                <Figure label="Range" value={values.length ? `${formatMultiple(Math.min(...values))} to ${formatMultiple(Math.max(...values))}` : "Not set"} />
                <Figure label="Comparables used" value={`${values.length} of ${database.length}`} />
              </dl>
              {database.length === 0 ? (
                <EmptyState>No reviewed comparable matches.</EmptyState>
              ) : (
                <ComparableTable
                  rows={database}
                  multiple={filters.multiple}
                  lead={(row) => (
                    <input
                      type="checkbox"
                      aria-label={`Use ${row.target} in the median`}
                      checked={!excluded.includes(row.id)}
                      onChange={() => setExcluded((ids) => (ids.includes(row.id) ? ids.filter((id) => id !== row.id) : [...ids, row.id]))}
                    />
                  )}
                  excluded={excluded}
                  tail={(row) => <span className="muted">{row.reviewer}</span>}
                  tailLabel="Reviewed by"
                />
              )}
            </section>

            {web.length > 0 && (
              <section className="card" aria-labelledby="web-title">
                <div className="card__head">
                  <h2 id="web-title" className="section-title">Unverified web results</h2>
                  <span className="card__meta">Not in the median and never in client documents until saved after review.</span>
                </div>
                <ComparableTable
                  rows={web}
                  multiple={filters.multiple}
                  excluded={[]}
                  tail={(row) => (
                    <button type="button" className="button button--small button--quiet button--row" onClick={() => act({ intent: "save", id: row.id }, `${row.target} saved to the database, reviewed by ${data.currentUserName}.`)}>
                      Save to database
                    </button>
                  )}
                  tailLabel="Review"
                />
              </section>
            )}
          </>
        )}
      </div>
    </>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="figures__item">
      <dt className="muted">{label}</dt>
      <dd className="figures__value">{value}</dd>
    </div>
  );
}

type TableProps = {
  rows: Comparable[];
  multiple: (typeof MULTIPLES)[number];
  excluded: string[];
  lead?: (row: Comparable) => React.ReactNode;
  tail: (row: Comparable) => React.ReactNode;
  tailLabel: string;
};

function ComparableTable({ rows, multiple, excluded, lead, tail, tailLabel }: TableProps) {
  return (
    <table className="table table--fixed">
      <colgroup>
        {lead && <col style={{ width: "40px" }} />}
        <col style={{ width: "15%" }} />
        <col style={{ width: "13%" }} />
        <col style={{ width: "11%" }} />
        <col style={{ width: "8%" }} />
        <col style={{ width: "10%" }} />
        <col style={{ width: "8%" }} />
        <col style={{ width: "8%" }} />
        <col style={{ width: "8%" }} />
        <col />
        <col style={{ width: "144px" }} />
      </colgroup>
      <thead>
        <tr>
          {lead && (
            <th scope="col">
              <span className="visually-hidden">Use in median</span>
            </th>
          )}
          <th scope="col">Target</th>
          <th scope="col">Acquirer</th>
          <th scope="col">Sector</th>
          <th scope="col">Geography</th>
          <th scope="col">Date</th>
          <th scope="col" className="num">EV</th>
          <th scope="col">Type</th>
          <th scope="col" className="num">{multiple}</th>
          <th scope="col">Source</th>
          <th scope="col">{tailLabel}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id} className={excluded.includes(row.id) ? "row--excluded" : undefined}>
            {lead && <td>{lead(row)}</td>}
            <td>
              <span className="cell-title cell-clip">{row.target}</span>
            </td>
            <td className="cell-clip">{row.acquirer}</td>
            <td className="cell-clip">{row.sector}</td>
            <td>{row.geography}</td>
            <td>{formatDate(row.date)}</td>
            <td className="num">{formatMoney(row.sizeUsd)}</td>
            <td>{row.type}</td>
            <td className="num">{formatMultiple(multipleOf(row, multiple))}</td>
            <td className="cell-clip">
              {row.verified ? (
                row.source
              ) : (
                <a href={`https://${row.source}`} target="_blank" rel="noreferrer">
                  {row.source}
                  <span className="visually-hidden"> (opens in a new tab)</span>
                </a>
              )}
            </td>
            <td>{tail(row)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
