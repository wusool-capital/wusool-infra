import { useState } from "react";
import { useSearchParams } from "react-router";
import { COUNTERPARTY_STATUSES, type DealViewData } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { anyOf, readList } from "../../lib/filters";
import { formatWhen } from "../../lib/format";
import { EmptyState } from "../ui/empty-state";
import { FilterBar } from "../ui/filter-bar";
import { StatusPill } from "./status-pill";
import { usePanel } from "./use-deal";

// PRD MB1 to MB3: the counterparty table. Enrichment never runs from here, only from a row's drawer.
export function BuyersTab({ data }: { data: DealViewData }) {
  const { openPanel } = usePanel();
  const [search, setSearch] = useState("");
  const [params] = useSearchParams();
  const statuses = readList(params, "status");
  const noun = data.deal.side === "sell" ? "buyers" : "targets";

  const rows = data.counterparties
    .filter((row) => anyOf(statuses, [row.status]))
    .filter((row) => row.name.toLowerCase().includes(search.trim().toLowerCase()))
    .sort((a, b) => COUNTERPARTY_STATUSES.indexOf(b.status === "Passed" ? "Not contacted" : b.status) - COUNTERPARTY_STATUSES.indexOf(a.status === "Passed" ? "Not contacted" : a.status));

  return (
    <>
      <FilterBar
        shown={rows.length}
        total={data.counterparties.length}
        before={
          <label className="toolbar__field">
            <span className="visually-hidden">Search {noun}</span>
            <input type="search" placeholder={`Search ${noun}`} value={search} onChange={(event) => setSearch(event.target.value)} />
          </label>
        }
        filters={[{ kind: "list", key: "status", label: "Status", options: [...COUNTERPARTY_STATUSES] }]}
      >
        <button type="button" className="button button--quiet" onClick={() => openPanel("find-more")}>
          Find more {noun}
        </button>
      </FilterBar>

      {rows.length === 0 ? (
        <EmptyState>No {noun} yet.</EmptyState>
      ) : (
        <div className="card card--flush">
          <table className="table table--fixed">
            <colgroup>
              <col style={{ width: "19%" }} />
              <col style={{ width: "20%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "11%" }} />
              <col />
              <col style={{ width: "15%" }} />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">{data.deal.side === "sell" ? "Buyer" : "Target"}</th>
                <th scope="col">Status</th>
                <th scope="col">Contacts</th>
                <th scope="col">Last contact</th>
                <th scope="col">Next step</th>
                <th scope="col">Data room</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const contacts = row.contactIds.map((id) => byId(data.people, id)?.name).filter(Boolean);
                return (
                  <tr
                    key={row.id}
                    className="row-clickable"
                    tabIndex={0}
                    onClick={() => openPanel(`buyer:${row.id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") openPanel(`buyer:${row.id}`);
                    }}
                  >
                    <td>
                      <span className="cell-title cell-clip">{row.name}</span>
                    </td>
                    <td>
                      <span className="status-cell">
                        <StatusPill status={row.status} />
                        {row.ndaSignedDate && <span className="chip">NDA</span>}
                      </span>
                    </td>
                    <td className="cell-clip" title={contacts.join(", ")}>
                      {contacts.length ? contacts.join(", ") : <span className="muted">No contact yet</span>}
                    </td>
                    <td>{row.lastContactAt ? formatWhen(row.lastContactAt, data.now) : <span className="muted">Not set</span>}</td>
                    <td className="cell-clip" title={row.nextStep}>{row.nextStep}</td>
                    <td>
                      {row.dataRoom ? (
                        <span className="cell-clip">
                          {formatWhen(row.dataRoom.lastViewAt, data.now)}, {row.dataRoom.filesOpened} files
                        </span>
                      ) : (
                        <span className="muted">No views</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
