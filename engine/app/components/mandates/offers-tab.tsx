import { useState } from "react";
import type { DealViewData, Offer } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { formatDate, formatMoney } from "../../lib/format";
import { EmptyState } from "../ui/empty-state";
import { usePanel } from "./use-deal";

const MAX_COMPARE = 3;

// PRD MO1 and MO2: offers received (sell-side) or sent (buy-side), compared side by side.
export function OffersTab({ data }: { data: DealViewData }) {
  const { openPanel } = usePanel();
  const [compare, setCompare] = useState<string[]>([]);
  const selected = data.offers.filter((offer) => compare.includes(offer.id));
  const name = (offer: Offer) => byId(data.counterparties, offer.counterpartyId)?.name ?? "Unknown";
  const toggle = (id: string) => setCompare(compare.includes(id) ? compare.filter((x) => x !== id) : [...compare, id].slice(-MAX_COMPARE));

  return (
    <>
      <div className="toolbar">
        <span className="muted">{data.deal.side === "sell" ? "Offers received from buyers." : "Offers sent to sellers."} Tick up to 3 to compare.</span>
        <button type="button" className="button button--quiet" onClick={() => openPanel("offer:new")}>
          Add offer
        </button>
      </div>

      {data.offers.length === 0 ? (
        <EmptyState>No offers yet.</EmptyState>
      ) : (
        <div className="card card--flush">
          <table className="table table--fixed">
            <colgroup>
              <col style={{ width: "6%" }} />
              <col style={{ width: "20%" }} />
              <col style={{ width: "7%" }} />
              <col style={{ width: "11%" }} />
              <col style={{ width: "10%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "9%" }} />
              <col />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">
                  <span className="visually-hidden">Compare</span>
                </th>
                <th scope="col">{data.deal.side === "sell" ? "Buyer" : "Target"}</th>
                <th scope="col">Type</th>
                <th scope="col">Date</th>
                <th scope="col" className="num">EV</th>
                <th scope="col" className="num">Cash</th>
                <th scope="col" className="num">DD weeks</th>
                <th scope="col">Status</th>
                <th scope="col">Conditions</th>
              </tr>
            </thead>
            <tbody>
              {data.offers.map((offer) => (
                <tr key={offer.id} className="row-clickable" tabIndex={0} onClick={() => openPanel(`offer:${offer.id}`)} onKeyDown={(event) => event.key === "Enter" && openPanel(`offer:${offer.id}`)}>
                  <td onClick={(event) => event.stopPropagation()}>
                    <input type="checkbox" aria-label={`Compare ${name(offer)}`} checked={compare.includes(offer.id)} onChange={() => toggle(offer.id)} />
                  </td>
                  <td><span className="cell-title">{name(offer)}</span></td>
                  <td>{offer.type}</td>
                  <td>{formatDate(offer.date)}</td>
                  <td className="num">{formatMoney(offer.evUsd)}</td>
                  <td className="num">{offer.cashPct}%</td>
                  <td className="num">{offer.ddWeeks}</td>
                  <td>{offer.status}</td>
                  <td className="cell-clip" title={offer.conditions}>{offer.conditions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected.length >= 2 && <Comparison offers={selected} name={name} />}
    </>
  );
}

const ROWS: { label: string; value: (offer: Offer) => string; numeric?: boolean }[] = [
  { label: "Type", value: (o) => o.type },
  { label: "Date", value: (o) => formatDate(o.date) },
  { label: "Enterprise value", value: (o) => formatMoney(o.evUsd), numeric: true },
  { label: "Cash at close", value: (o) => `${o.cashPct}%`, numeric: true },
  { label: "Deferred", value: (o) => `${o.deferredPct}%`, numeric: true },
  { label: "Earn-out", value: (o) => `${o.earnoutPct}%`, numeric: true },
  { label: "Due diligence", value: (o) => `${o.ddWeeks} weeks`, numeric: true },
  { label: "Exclusivity asked", value: (o) => `${o.exclusivityWeeks} weeks`, numeric: true },
  { label: "Conditions", value: (o) => o.conditions },
  { label: "Status", value: (o) => o.status },
  { label: "Document", value: (o) => o.documentName ?? "Not set" },
];

function Comparison({ offers, name }: { offers: Offer[]; name: (offer: Offer) => string }) {
  return (
    <section className="card compare" aria-labelledby="compare-title">
      <div className="card__head">
        <h2 id="compare-title" className="section-title">Side by side</h2>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Term</th>
            {offers.map((offer) => (
              <th key={offer.id} scope="col">
                {name(offer)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.label}>
              <th scope="row" className="compare__label">{row.label}</th>
              {offers.map((offer) => (
                <td key={offer.id} className={row.numeric ? "num" : undefined}>
                  {row.value(offer)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
